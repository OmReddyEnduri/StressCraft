"""
StressCraft Runners
===================
Subprocess execution and compiler wrapper for Competitive Programming solutions
(C++, Python, Rust, Go, Java). Measures execution time, memory usage,
and enforces timeouts with clean process-tree termination.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, Union

from stresscraft.models import Language, RunResult, RunStatus


class CompilationError(Exception):
    """Raised when source code compilation fails."""

    def __init__(self, message: str, stderr: str = "", exit_code: int = 1) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.exit_code = exit_code


class SourceRunner:
    """Compiles and executes solution source files across supported languages."""

    def __init__(
        self,
        source_path: str | Path,
        language: Optional[Language] = None,
        cxx_compiler: Optional[str] = None,
        cxx_flags: Optional[list[str]] = None,
        rust_compiler: Optional[str] = None,
        rust_flags: Optional[list[str]] = None,
        python_executable: Optional[str] = None,
    ) -> None:
        self.source_path = Path(source_path).resolve()
        if not self.source_path.exists():
            raise FileNotFoundError(f"Source file not found: {self.source_path}")

        self.language = language or Language.from_extension(self.source_path)
        self.cxx_compiler = cxx_compiler or os.environ.get("STRESSCRAFT_CXX", "g++")
        self.cxx_flags = cxx_flags or ["-O3", "-std=c++20"]
        self.rust_compiler = rust_compiler or os.environ.get("STRESSCRAFT_RUSTC", "rustc")
        self.rust_flags = rust_flags or ["-O"]
        self.python_executable = python_executable or sys.executable

        self._temp_dir: Optional[tempfile.TemporaryDirectory[str]] = None
        self.executable_path: Optional[Path] = None
        self._compiled: bool = False
        self._compilation_error: Optional[str] = None

        self._prepare()

    @classmethod
    def from_code(
        cls,
        code: str,
        language: Language,
        suffix: Optional[str] = None,
        **kwargs,
    ) -> SourceRunner:
        """Create a runner from inline source code string."""
        ext_map = {
            Language.CPP: ".cpp",
            Language.PYTHON: ".py",
            Language.RUST: ".rs",
            Language.GO: ".go",
            Language.JAVA: ".java",
        }
        ext = suffix or ext_map.get(language, ".txt")
        temp_dir = tempfile.mkdtemp(prefix="stresscraft_inline_")
        source_file = Path(temp_dir) / f"solution{ext}"
        source_file.write_text(code, encoding="utf-8")
        runner = cls(source_file, language=language, **kwargs)
        runner._owns_temp_dir = temp_dir
        return runner

    def _prepare(self) -> None:
        """Compile source if required or set up execution target."""
        if self.language == Language.PYTHON:
            self.executable_path = self.source_path
            self._compiled = True
            return

        self._temp_dir = tempfile.TemporaryDirectory(prefix="stresscraft_build_")
        build_dir = Path(self._temp_dir.name)
        exe_ext = ".exe" if sys.platform == "win32" else ""
        out_binary = build_dir / f"solution{exe_ext}"

        if self.language == Language.CPP:
            cmd = [self.cxx_compiler, *self.cxx_flags, str(self.source_path), "-o", str(out_binary)]
        elif self.language == Language.RUST:
            cmd = [self.rust_compiler, *self.rust_flags, str(self.source_path), "-o", str(out_binary)]
        elif self.language == Language.GO:
            cmd = ["go", "build", "-o", str(out_binary), str(self.source_path)]
        elif self.language == Language.JAVA:
            cmd = ["javac", "-d", str(build_dir), str(self.source_path)]
        else:
            raise ValueError(f"Unsupported compilation for language: {self.language}")

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                self._compilation_error = res.stderr or res.stdout
                self._compiled = False
            else:
                self.executable_path = out_binary
                self._compiled = True
        except FileNotFoundError as e:
            self._compilation_error = f"Compiler executable not found for {self.language}: {e}"
            self._compiled = False

    def run(
        self,
        input_data: str,
        timeout_sec: float = 2.0,
    ) -> RunResult:
        """Execute the solution on input_data and return RunResult."""
        if not self._compiled or self._compilation_error:
            return RunResult(
                status=RunStatus.CE,
                stderr=self._compilation_error or "Compilation failed",
                compilation_error=self._compilation_error,
                exit_code=1,
            )

        if self.language == Language.PYTHON:
            cmd = [self.python_executable, "-u", str(self.executable_path)]
        elif self.language == Language.JAVA:
            class_name = self.source_path.stem
            cmd = ["java", "-cp", str(self._temp_dir.name if self._temp_dir else "."), class_name]
        else:
            cmd = [str(self.executable_path)]

        start_time = time.perf_counter()
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return RunResult(
                time_ms=elapsed_ms,
                status=RunStatus.RTE,
                stderr=f"Failed to launch process: {e}",
                exit_code=-1,
            )

        input_bytes = input_data.encode("utf-8")
        try:
            out_bytes, err_bytes = proc.communicate(input=input_bytes, timeout=timeout_sec)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
        except subprocess.TimeoutExpired:
            self._kill_process(proc)
            try:
                out_bytes, err_bytes = proc.communicate(timeout=0.2)
            except Exception:
                out_bytes, err_bytes = b"", b""
            return RunResult(
                time_ms=timeout_sec * 1000,
                status=RunStatus.TLE,
                stdout=out_bytes.decode("utf-8", errors="replace"),
                stderr=err_bytes.decode("utf-8", errors="replace") + "\n[StressCraft: Execution Timed Out]",
                exit_code=-1,
            )

        stdout_str = out_bytes.decode("utf-8", errors="replace")
        stderr_str = err_bytes.decode("utf-8", errors="replace")
        exit_code = proc.returncode

        status = RunStatus.OK if exit_code == 0 else RunStatus.RTE

        # Best-effort memory measurement
        memory_kb = self._get_memory_estimate(proc.pid)

        return RunResult(
            time_ms=elapsed_ms,
            memory_kb=memory_kb,
            stdout=stdout_str,
            stderr=stderr_str,
            status=status,
            exit_code=exit_code,
        )

    def _kill_process(self, proc: subprocess.Popen) -> None:
        """Cleanly terminate process and any spawned child processes."""
        try:
            proc.kill()
        except Exception:
            pass

        try:
            proc.wait(timeout=0.2)
        except Exception:
            pass

        if sys.platform == "win32":
            try:
                subprocess.call(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=0.5,
                )
            except Exception:
                pass

    def _get_memory_estimate(self, pid: int) -> float:
        """Best-effort process peak working set in KB."""
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                    ]

                PROCESS_QUERY_INFORMATION = 0x0400
                PROCESS_VM_READ = 0x0010
                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid
                )
                if handle:
                    try:
                        counters = PROCESS_MEMORY_COUNTERS()
                        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                        if ctypes.windll.psapi.GetProcessMemoryInfo(
                            handle, ctypes.byref(counters), counters.cb
                        ):
                            return float(counters.PeakWorkingSetSize / 1024.0)
                    finally:
                        ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                return 0.0
        return 0.0

    def cleanup(self) -> None:
        """Clean up any temporary compilation artifacts."""
        if self._temp_dir:
            try:
                self._temp_dir.cleanup()
            except Exception:
                pass
            self._temp_dir = None
        if hasattr(self, "_owns_temp_dir"):
            try:
                shutil.rmtree(self._owns_temp_dir, ignore_errors=True)
            except Exception:
                pass

    def __enter__(self) -> SourceRunner:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()

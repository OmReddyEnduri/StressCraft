"""
StressCraft Models
==================
Core data structures, enums, and reports for the StressCraft differential fuzzing engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class Language(str, Enum):
    """Supported programming languages for candidate and reference solutions."""
    CPP = "CPP"
    PYTHON = "PYTHON"
    RUST = "RUST"
    GO = "GO"
    JAVA = "JAVA"

    @classmethod
    def from_extension(cls, file_path: str | Path) -> Language:
        """Deduce language from file extension."""
        path = Path(file_path)
        ext = path.suffix.lower()
        mapping = {
            ".cpp": cls.CPP,
            ".cc": cls.CPP,
            ".cxx": cls.CPP,
            ".c++": cls.CPP,
            ".cp": cls.CPP,
            ".py": cls.PYTHON,
            ".pyw": cls.PYTHON,
            ".rs": cls.RUST,
            ".go": cls.GO,
            ".java": cls.JAVA,
        }
        if ext in mapping:
            return mapping[ext]
        raise ValueError(f"Unsupported file extension '{ext}' for path: {file_path}")

    @classmethod
    def from_string(cls, name: str) -> Language:
        """Parse language from string name (case-insensitive)."""
        upper = name.strip().upper()
        aliases = {
            "C++": cls.CPP,
            "G++": cls.CPP,
            "PY": cls.PYTHON,
            "PYTHON3": cls.PYTHON,
            "RS": cls.RUST,
            "GOLANG": cls.GO,
        }
        if upper in aliases:
            return aliases[upper]
        try:
            return cls(upper)
        except ValueError:
            raise ValueError(f"Unknown language identifier: {name}")


class RunStatus(str, Enum):
    """Execution status for a solution run."""
    OK = "OK"    # Completed normally with exit code 0
    TLE = "TLE"  # Time Limit Exceeded
    MLE = "MLE"  # Memory Limit Exceeded
    RTE = "RTE"  # Runtime Error (non-zero exit code or signal)
    CE = "CE"    # Compilation Error


@dataclass
class RunResult:
    """Outcome of running a program on a given testcase."""
    time_ms: float = 0.0
    memory_kb: float = 0.0
    stdout: str = ""
    stderr: str = ""
    status: RunStatus = RunStatus.OK
    exit_code: int = 0
    compilation_error: Optional[str] = None

    @property
    def is_ok(self) -> bool:
        """Returns True if execution completed successfully."""
        return self.status == RunStatus.OK and self.exit_code == 0

    @property
    def is_tle(self) -> bool:
        """Returns True if execution timed out."""
        return self.status == RunStatus.TLE

    @property
    def is_rte(self) -> bool:
        """Returns True if execution crashed with a runtime error."""
        return self.status == RunStatus.RTE

    @property
    def is_ce(self) -> bool:
        """Returns True if source code failed compilation."""
        return self.status == RunStatus.CE


@dataclass
class ComparisonResult:
    """Detailed diff comparison between expected and actual outputs."""
    match: bool
    diff_details: str = ""
    expected_token: Optional[str] = None
    actual_token: Optional[str] = None
    line_number: Optional[int] = None
    token_index: Optional[int] = None

    def __bool__(self) -> bool:
        return self.match


@dataclass
class Counterexample:
    """A single failing test case discovered during fuzzing."""
    input_data: str
    candidate_result: RunResult
    reference_result: RunResult
    comparison: ComparisonResult
    run_index: int = 0

    @property
    def failure_type(self) -> str:
        """Classify the failure into TLE, RTE, or WA (Wrong Answer)."""
        if self.candidate_result.is_tle:
            return "TLE"
        if self.candidate_result.is_rte:
            return "RTE"
        if not self.comparison.match:
            return "WA"
        return "UNKNOWN"


@dataclass
class FuzzReport:
    """Summary report of a differential fuzzing run."""
    total_runs: int
    passed_runs: int
    counterexamples_found: int
    minimal_case: Optional[str] = None
    counterexamples: list[Counterexample] = field(default_factory=list)
    duration_sec: float = 0.0

    @property
    def success(self) -> bool:
        """Returns True if no counterexamples were detected."""
        return self.counterexamples_found == 0

    def summary(self) -> str:
        """Human-readable summary of fuzzing results."""
        lines = [
            "=" * 50,
            "StressCraft Differential Fuzz Report",
            "=" * 50,
            f"Total Iterations:       {self.total_runs}",
            f"Passed Iterations:      {self.passed_runs}",
            f"Counterexamples Found:  {self.counterexamples_found}",
            f"Duration:               {self.duration_sec:.2f}s",
        ]
        if self.counterexamples_found > 0:
            first = self.counterexamples[0]
            lines.append(f"Primary Failure Type:   {first.failure_type}")
            if self.minimal_case is not None:
                lines.extend([
                    "-" * 50,
                    "Minimal Reproducible Counterexample:",
                    "-" * 50,
                    self.minimal_case.strip(),
                    "-" * 50,
                ])
        else:
            lines.append("Status: ALL TESTS PASSED")
        lines.append("=" * 50)
        return "\n".join(lines)

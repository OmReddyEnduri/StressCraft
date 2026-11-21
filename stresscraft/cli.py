"""
StressCraft CLI
===============
Interactive Rich terminal CLI for automated competitive programming differential fuzzing,
testcase generation, counterexample minimization, and asymptotic profiling.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from stresscraft import __version__
from stresscraft.differ import OutputComparator
from stresscraft.fuzzer import StressFuzzer
from stresscraft.generators import RandomGenerator
from stresscraft.minimizer import DeltaDebugger
from stresscraft.models import ComparisonResult, Counterexample, FuzzReport, Language, RunResult, RunStatus
from stresscraft.runners import SourceRunner


console = Console()


def create_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser for the StressCraft CLI."""
    parser = argparse.ArgumentParser(
        prog="stresscraft",
        description="High-performance automated competitive programming differential fuzzing and minimization engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--version", action="version", version=f"StressCraft v{__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # -------------------------------------------------------------------------
    # stresscraft fuzz
    # -------------------------------------------------------------------------
    fuzz_parser = subparsers.add_parser(
        "fuzz",
        help="Run differential fuzzing between candidate and reference solutions",
        description="Concurrently fuzzes candidate solution against a reference solution using random testcases.",
    )
    fuzz_parser.add_argument("candidate", help="Path to candidate solution source file (C++, Python, Rust, etc.)")
    fuzz_parser.add_argument("reference", help="Path to reference/brute force solution source file")
    fuzz_parser.add_argument(
        "-g", "--generator", "-t", "--template",
        dest="template",
        default="n=int(1,10); a=array(n, 1, 100)",
        help="Template DSL string or generator expression (default: 'n=int(1,10); a=array(n, 1, 100)')",
    )
    fuzz_parser.add_argument(
        "--gen-file",
        help="Path to external generator script or template file",
    )
    fuzz_parser.add_argument(
        "-n", "--iterations",
        type=int,
        default=100,
        help="Total number of fuzzing testcases to generate and evaluate (default: 100)",
    )
    fuzz_parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Timeout per testcase in seconds (default: 2.0)",
    )
    fuzz_parser.add_argument(
        "-c", "--compare",
        choices=["tokens", "exact", "float"],
        default="tokens",
        help="Output comparison mode: tokens (default), exact, or float",
    )
    fuzz_parser.add_argument(
        "--eps",
        type=float,
        default=1e-6,
        help="Tolerance epsilon for float comparison mode (default: 1e-6)",
    )
    fuzz_parser.add_argument(
        "--no-minimize",
        action="store_true",
        help="Disable automatic delta-debugging minimization of counterexamples",
    )
    fuzz_parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue fuzzing across all iterations even after discovering a failure",
    )
    fuzz_parser.add_argument(
        "-o", "--output",
        help="Optional path to save minimal counterexample testcase to a file",
    )

    # -------------------------------------------------------------------------
    # stresscraft minimize
    # -------------------------------------------------------------------------
    min_parser = subparsers.add_parser(
        "minimize",
        help="Run delta-debugger to shrink a failing testcase to minimal size",
        description="Shrinks large failing testcases to minimal counterexamples using hierarchical delta debugging.",
    )
    min_parser.add_argument("-i", "--input", required=True, help="Path to file containing failing testcase, or raw string")
    min_parser.add_argument("-c", "--candidate", required=True, help="Path to candidate solution")
    min_parser.add_argument("-r", "--reference", required=True, help="Path to reference solution")
    min_parser.add_argument("--timeout", type=float, default=2.0, help="Per-run execution timeout in seconds")
    min_parser.add_argument("-o", "--output", help="Optional output file path to write minimized testcase")

    # -------------------------------------------------------------------------
    # stresscraft gen
    # -------------------------------------------------------------------------
    gen_parser = subparsers.add_parser(
        "gen",
        help="Generate random testcases from CLI options or template DSL",
        description="Generates randomized testcases for arrays, permutations, trees, graphs, grids, or strings.",
    )
    gen_parser.add_argument("-t", "--template", help="Template DSL expression (e.g. 'n=int(5,10); a=array(n, 1, 100)')")
    gen_parser.add_argument(
        "--type",
        choices=["array", "permutation", "tree", "graph", "string", "grid", "int"],
        help="Type of data structure to generate when not using a full template",
    )
    gen_parser.add_argument("-n", "--size", type=int, default=10, help="Size parameter (n) for array, tree, graph, etc.")
    gen_parser.add_argument("--min-val", type=int, default=1, help="Minimum integer value (default: 1)")
    gen_parser.add_argument("--max-val", type=int, default=100, help="Maximum integer value (default: 100)")
    gen_parser.add_argument("--sorted", action="store_true", help="Generate array in sorted ascending order")
    gen_parser.add_argument("--distinct", action="store_true", help="Generate distinct unique elements")
    gen_parser.add_argument("--directed", action="store_true", help="Generate directed graph")
    gen_parser.add_argument("--weighted", action="store_true", help="Generate weighted graph edges")
    gen_parser.add_argument("-m", "--edges", type=int, help="Number of edges for graph (default: n - 1)")
    gen_parser.add_argument("--rows", type=int, default=3, help="Grid rows count")
    gen_parser.add_argument("--cols", type=int, default=3, help="Grid columns count")
    gen_parser.add_argument("--alphabet", default="abcdefghijklmnopqrstuvwxyz", help="Alphabet for string generation")
    gen_parser.add_argument("--seed", type=int, help="Deterministic random seed")
    gen_parser.add_argument("-c", "--count", type=int, default=1, help="Number of testcases to generate (default: 1)")
    gen_parser.add_argument("-o", "--output", help="Output file path (default: stdout)")

    # -------------------------------------------------------------------------
    # stresscraft bench
    # -------------------------------------------------------------------------
    bench_parser = subparsers.add_parser(
        "bench",
        help="Profile runtime and memory across scale (N=10 to N=100000) to find asymptotic bottlenecks",
        description="Evaluates candidate solution across escalating scale factors to detect TLE and asymptotic complexity.",
    )
    bench_parser.add_argument("solution", help="Path to solution source file to benchmark")
    bench_parser.add_argument(
        "-s", "--scales",
        default="10,100,1000,10000,100000",
        help="Comma-separated input scales N (default: '10,100,1000,10000,100000')",
    )
    bench_parser.add_argument(
        "-t", "--template",
        default="n={N}; a=array(n, 1, 1000000)",
        help="Template pattern with {N} placeholder for scale value (default: 'n={N}; a=array(n, 1, 1000000)')",
    )
    bench_parser.add_argument("-r", "--runs", type=int, default=3, help="Benchmark runs per scale to average (default: 3)")
    bench_parser.add_argument("--timeout", type=float, default=10.0, help="Per-run timeout limit in seconds (default: 10.0)")

    return parser


def handle_fuzz(args: argparse.Namespace) -> int:
    """Handle `stresscraft fuzz` command."""
    cand_path = Path(args.candidate)
    ref_path = Path(args.reference)

    if not cand_path.exists():
        console.print(f"[bold red]Error:[/bold red] Candidate file not found: [yellow]{cand_path}[/yellow]")
        return 1
    if not ref_path.exists():
        console.print(f"[bold red]Error:[/bold red] Reference file not found: [yellow]{ref_path}[/yellow]")
        return 1

    template_str = args.template
    if args.gen_file:
        gen_file_path = Path(args.gen_file)
        if not gen_file_path.exists():
            console.print(f"[bold red]Error:[/bold red] Generator file not found: [yellow]{gen_file_path}[/yellow]")
            return 1
        template_str = gen_file_path.read_text(encoding="utf-8")

    console.print(
        Panel(
            f"[bold cyan]StressCraft Differential Fuzzing Engine[/bold cyan]\n"
            f"Candidate: [yellow]{cand_path.name}[/yellow] | Reference: [green]{ref_path.name}[/green]\n"
            f"Iterations: [magenta]{args.iterations}[/magenta] | Timeout: [magenta]{args.timeout}s[/magenta] | Mode: [magenta]{args.compare}[/magenta]\n"
            f"Template:  [dim]{template_str}[/dim]",
            title="[bold blue]Fuzz Session[/bold blue]",
            border_style="cyan",
        )
    )

    try:
        cand_runner = SourceRunner(cand_path)
    except Exception as e:
        console.print(f"[bold red]Failed to prepare candidate solution:[/bold red] {e}")
        return 1

    try:
        ref_runner = SourceRunner(ref_path)
    except Exception as e:
        cand_runner.cleanup()
        console.print(f"[bold red]Failed to prepare reference solution:[/bold red] {e}")
        return 1

    rng = RandomGenerator()
    comparator = OutputComparator()
    minimizer = DeltaDebugger(comparator=comparator)

    stop_on_first = not args.keep_going
    do_minimize = not args.no_minimize

    passed = 0
    failures: list[Counterexample] = []
    minimal_case: Optional[str] = None

    if args.compare == "exact":
        cmp_fn = comparator.compare_exact
    elif args.compare == "float":
        cmp_fn = lambda exp, act: comparator.compare_float(exp, act, eps=args.eps)
    else:
        cmp_fn = comparator.compare_tokens

    start_time = time.perf_counter()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("• Passed: [green]{task.fields[passed]}[/green]"),
        TextColumn("• Failed: [red]{task.fields[failed]}[/red]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "Fuzzing...",
            total=args.iterations,
            passed=0,
            failed=0,
        )

        for i in range(1, args.iterations + 1):
            try:
                test_input = rng.from_template(template_str)
            except Exception as e:
                console.print(f"[bold red]Generator template error on iteration {i}:[/bold red] {e}")
                cand_runner.cleanup()
                ref_runner.cleanup()
                return 1

            ref_res = ref_runner.run(test_input, timeout_sec=args.timeout)
            cand_res = cand_runner.run(test_input, timeout_sec=args.timeout)

            is_fail = False
            cmp_res = ComparisonResult(match=True)

            if cand_res.is_tle and not ref_res.is_tle:
                is_fail = True
                cmp_res = ComparisonResult(match=False, diff_details="Candidate timed out (TLE)")
            elif cand_res.is_rte and not ref_res.is_rte:
                is_fail = True
                cmp_res = ComparisonResult(match=False, diff_details=f"Candidate crashed (RTE):\n{cand_res.stderr}")
            elif not cand_res.is_ok and ref_res.is_ok:
                is_fail = True
                cmp_res = ComparisonResult(match=False, diff_details=f"Candidate error status: {cand_res.status}")
            else:
                cmp_res = cmp_fn(ref_res.stdout, cand_res.stdout)
                if not cmp_res.match:
                    is_fail = True

            if is_fail:
                ce = Counterexample(
                    input_data=test_input,
                    candidate_result=cand_res,
                    reference_result=ref_res,
                    comparison=cmp_res,
                    run_index=i,
                )
                failures.append(ce)
                progress.update(task, advance=1, failed=len(failures))

                if do_minimize and minimal_case is None:
                    progress.console.print("\n[bold yellow]⚡ Counterexample detected! Launching DeltaDebugger minimization...[/bold yellow]")
                    minimal_case = minimizer.minimize(
                        input_data=test_input,
                        candidate=cand_runner,
                        reference=ref_runner,
                        timeout_sec=args.timeout,
                    )

                if stop_on_first:
                    break
            else:
                passed += 1
                progress.update(task, advance=1, passed=passed)

    duration = time.perf_counter() - start_time
    cand_runner.cleanup()
    ref_runner.cleanup()

    if failures:
        first = failures[0]
        # Display failure panel
        details_table = Table(show_header=True, header_style="bold magenta", expand=True)
        details_table.add_column("Property", style="bold cyan", width=18)
        details_table.add_column("Candidate (Failed)", style="yellow")
        details_table.add_column("Reference (Expected)", style="green")

        details_table.add_row("Status", str(first.candidate_result.status.value), str(first.reference_result.status.value))
        details_table.add_row("Exit Code", str(first.candidate_result.exit_code), str(first.reference_result.exit_code))
        details_table.add_row("Runtime", f"{first.candidate_result.time_ms:.1f} ms", f"{first.reference_result.time_ms:.1f} ms")
        details_table.add_row(
            "Output (Stdout)",
            first.candidate_result.stdout.strip() or "<empty>",
            first.reference_result.stdout.strip() or "<empty>",
        )
        if first.candidate_result.stderr.strip():
            details_table.add_row("Stderr", first.candidate_result.stderr.strip(), "")

        content = [
            f"[bold red]❌ FAILURE DETECTED on iteration #{first.run_index}[/bold red]",
            f"Failure Classification: [bold red]{first.failure_type}[/bold red]",
            f"Diff: {first.comparison.diff_details}",
            "",
            "[bold white]Execution Comparison:[/bold white]",
        ]

        console.print(
            Panel(
                "\n".join(content),
                title="[bold red]Counterexample Discovered[/bold red]",
                border_style="red",
            )
        )
        console.print(details_table)

        min_display = minimal_case or first.input_data
        console.print(
            Panel(
                f"[bold green]Minimal Reproducible Testcase:[/bold green]\n\n"
                f"[bold white]{min_display.strip()}[/bold white]",
                title="[bold yellow]Delta-Debugging Minimized Input[/bold yellow]",
                border_style="yellow",
            )
        )

        if args.output:
            out_p = Path(args.output)
            out_p.write_text(min_display, encoding="utf-8")
            console.print(f"[bold green]Saved minimal counterexample to:[/bold green] {out_p}")

        return 1

    # All iterations passed
    console.print(
        Panel(
            f"[bold green]✔ ALL {passed} ITERATIONS PASSED[/bold green]\n"
            f"No counterexamples found in [cyan]{duration:.2f}s[/cyan].\n"
            f"Candidate solution is differentially consistent with reference.",
            title="[bold green]Fuzzing Complete[/bold green]",
            border_style="green",
        )
    )
    return 0


def handle_minimize(args: argparse.Namespace) -> int:
    """Handle `stresscraft minimize` command."""
    input_str = args.input
    in_path = Path(input_str)
    if in_path.exists() and in_path.is_file():
        test_input = in_path.read_text(encoding="utf-8")
    else:
        test_input = input_str

    cand_path = Path(args.candidate)
    ref_path = Path(args.reference)

    if not cand_path.exists():
        console.print(f"[bold red]Error:[/bold red] Candidate file not found: {cand_path}")
        return 1
    if not ref_path.exists():
        console.print(f"[bold red]Error:[/bold red] Reference file not found: {ref_path}")
        return 1

    try:
        cand_runner = SourceRunner(cand_path)
        ref_runner = SourceRunner(ref_path)
    except Exception as e:
        console.print(f"[bold red]Failed to prepare solution runners:[/bold red] {e}")
        return 1

    console.print(
        Panel(
            f"Starting Delta-Debugging Minimization on testcase ({len(test_input)} chars, {len(test_input.splitlines())} lines)...",
            title="[bold yellow]StressCraft Delta Debugger[/bold yellow]",
            border_style="yellow",
        )
    )

    debugger = DeltaDebugger()
    start_t = time.perf_counter()
    reduced = debugger.minimize(
        test_input,
        candidate=cand_runner,
        reference=ref_runner,
        timeout_sec=args.timeout,
    )
    duration = time.perf_counter() - start_t

    cand_runner.cleanup()
    ref_runner.cleanup()

    orig_lines = len(test_input.splitlines())
    red_lines = len(reduced.splitlines())
    orig_chars = len(test_input)
    red_chars = len(reduced)
    compression = (1.0 - (red_chars / max(1, orig_chars))) * 100

    console.print(
        Panel(
            f"[bold green]Minimized Counterexample ({red_chars} chars, {red_lines} lines | {compression:.1f}% reduction in {duration:.2f}s):[/bold green]\n\n"
            f"[bold white]{reduced.strip()}[/bold white]",
            title="[bold green]Minimization Result[/bold green]",
            border_style="green",
        )
    )

    if args.output:
        out_p = Path(args.output)
        out_p.write_text(reduced, encoding="utf-8")
        console.print(f"[bold green]Saved minimized input to:[/bold green] {out_p}")

    return 0


def handle_gen(args: argparse.Namespace) -> int:
    """Handle `stresscraft gen` command."""
    rng = RandomGenerator(seed=args.seed)

    generated_cases: list[str] = []

    for _ in range(args.count):
        if args.template:
            val = rng.from_template(args.template)
            generated_cases.append(val)
        elif args.type:
            if args.type == "array":
                arr = rng.array(
                    args.size,
                    args.min_val,
                    args.max_val,
                    sorted=args.sorted,
                    distinct=args.distinct,
                )
                generated_cases.append(f"{len(arr)}\n" + " ".join(str(x) for x in arr))
            elif args.type == "permutation":
                perm = rng.permutation(args.size)
                generated_cases.append(f"{len(perm)}\n" + " ".join(str(x) for x in perm))
            elif args.type == "tree":
                edges = rng.tree(args.size)
                lines = [f"{args.size}"]
                for u, v in edges:
                    lines.append(f"{u} {v}")
                generated_cases.append("\n".join(lines))
            elif args.type == "graph":
                m = args.edges if args.edges is not None else max(1, args.size - 1)
                edges = rng.graph(
                    args.size,
                    m,
                    directed=args.directed,
                    weighted=args.weighted,
                    min_w=args.min_val,
                    max_w=args.max_val,
                )
                lines = [f"{args.size} {len(edges)}"]
                for e in edges:
                    lines.append(" ".join(str(x) for x in e))
                generated_cases.append("\n".join(lines))
            elif args.type == "string":
                s = rng.string(args.size, alphabet=args.alphabet)
                generated_cases.append(s)
            elif args.type == "grid":
                grid = rng.grid(args.rows, args.cols, min_val=args.min_val, max_val=args.max_val)
                lines = [f"{args.rows} {args.cols}"]
                for row in grid:
                    lines.append(" ".join(str(x) for row_x in row for x in [row_x]))
                generated_cases.append("\n".join(lines))
            elif args.type == "int":
                i_val = rng.integer(args.min_val, args.max_val)
                generated_cases.append(str(i_val))
        else:
            # Default array generation
            arr = rng.array(args.size, args.min_val, args.max_val)
            generated_cases.append(f"{len(arr)}\n" + " ".join(str(x) for x in arr))

    full_output = "\n".join(generated_cases)

    if args.output:
        out_p = Path(args.output)
        out_p.write_text(full_output, encoding="utf-8")
        console.print(f"[bold green]Generated {len(generated_cases)} testcase(s) saved to:[/bold green] {out_p}")
    else:
        # Standard stdout output for easy piping
        sys.stdout.write(full_output + "\n")
        sys.stdout.flush()

    return 0


def handle_bench(args: argparse.Namespace) -> int:
    """Handle `stresscraft bench` command."""
    sol_path = Path(args.solution)
    if not sol_path.exists():
        console.print(f"[bold red]Error:[/bold red] Solution file not found: {sol_path}")
        return 1

    try:
        runner = SourceRunner(sol_path)
    except Exception as e:
        console.print(f"[bold red]Failed to prepare solution runner:[/bold red] {e}")
        return 1

    scales: list[int] = []
    for s_str in args.scales.split(","):
        s_clean = s_str.strip()
        if s_clean:
            try:
                scales.append(int(s_clean))
            except ValueError:
                console.print(f"[bold red]Invalid scale integer:[/bold red] {s_clean}")
                runner.cleanup()
                return 1

    console.print(
        Panel(
            f"[bold cyan]StressCraft Asymptotic Profiler[/bold cyan]\n"
            f"Target: [yellow]{sol_path.name}[/yellow] | Runs per scale: [magenta]{args.runs}[/magenta] | Timeout: [magenta]{args.timeout}s[/magenta]\n"
            f"Scales: [green]{scales}[/green]\n"
            f"Template: [dim]{args.template}[/dim]",
            title="[bold blue]Benchmarking Session[/bold blue]",
            border_style="cyan",
        )
    )

    rng = RandomGenerator()
    results_table = Table(title="Asymptotic Performance Benchmark", show_header=True, header_style="bold magenta")
    results_table.add_column("Scale (N)", justify="right", style="cyan")
    results_table.add_column("Runs", justify="center", style="dim")
    results_table.add_column("Avg Time (ms)", justify="right", style="green")
    results_table.add_column("Peak Mem (KB)", justify="right", style="yellow")
    results_table.add_column("Status", justify="center", style="bold")
    results_table.add_column("Growth Ratio", justify="right", style="magenta")

    prev_time = None
    prev_n = None

    for n in scales:
        tmpl = args.template.replace("{N}", str(n))
        times: list[float] = []
        mems: list[float] = []
        status = "OK"

        for _ in range(args.runs):
            test_input = rng.from_template(tmpl)
            res = runner.run(test_input, timeout_sec=args.timeout)
            if not res.is_ok:
                status = res.status.value
                times.append(res.time_ms)
                mems.append(res.memory_kb)
                break
            times.append(res.time_ms)
            mems.append(res.memory_kb)

        avg_time = sum(times) / max(1, len(times))
        max_mem = max(mems) if mems else 0.0

        growth_str = "-"
        if prev_time is not None and prev_time > 0 and prev_n is not None and prev_n > 0:
            time_ratio = avg_time / prev_time
            n_ratio = n / prev_n
            growth_str = f"{time_ratio:.2f}x (N: {n_ratio:.0f}x)"

        prev_time = avg_time
        prev_n = n

        status_style = "green" if status == "OK" else "red"
        results_table.add_row(
            f"{n:,}",
            str(len(times)),
            f"{avg_time:.2f}",
            f"{max_mem:,.1f}",
            f"[{status_style}]{status}[/{status_style}]",
            growth_str,
        )

        if status != "OK":
            console.print(f"[bold red]Bottleneck hit at N={n:,}: Status {status}[/bold red]")
            break

    runner.cleanup()
    console.print(results_table)
    return 0


def main(args: Optional[Sequence[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = create_parser()
    if args is None:
        args = sys.argv[1:]

    if not args:
        parser.print_help()
        return 0

    parsed_args = parser.parse_args(args)

    if parsed_args.command == "fuzz":
        return handle_fuzz(parsed_args)
    elif parsed_args.command == "minimize":
        return handle_minimize(parsed_args)
    elif parsed_args.command == "gen":
        return handle_gen(parsed_args)
    elif parsed_args.command == "bench":
        return handle_bench(parsed_args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

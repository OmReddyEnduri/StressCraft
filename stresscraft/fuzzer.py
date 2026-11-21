"""
StressCraft Differential Fuzzing Engine
=======================================
Coordinates fuzzing sessions by driving testcase generation, executing candidate
and reference solutions, validating outputs with differential comparators,
and shrinking counterexamples with DeltaDebugger.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional, Union

from stresscraft.differ import OutputComparator
from stresscraft.generators import RandomGenerator
from stresscraft.minimizer import DeltaDebugger
from stresscraft.models import (
    ComparisonResult,
    Counterexample,
    FuzzReport,
    Language,
    RunResult,
    RunStatus,
)
from stresscraft.runners import SourceRunner


class StressFuzzer:
    """Differential fuzzing engine for Competitive Programming."""

    def __init__(
        self,
        candidate: Union[SourceRunner, str, Path],
        reference: Union[SourceRunner, str, Path],
        generator: Union[RandomGenerator, Callable[[], str], str],
        comparator: Optional[OutputComparator] = None,
        minimizer: Optional[DeltaDebugger] = None,
        candidate_lang: Optional[Language] = None,
        reference_lang: Optional[Language] = None,
    ) -> None:
        # Wrap candidate runner
        if isinstance(candidate, SourceRunner):
            self.candidate = candidate
            self._owns_candidate = False
        else:
            self.candidate = SourceRunner(candidate, language=candidate_lang)
            self._owns_candidate = True

        # Wrap reference runner
        if isinstance(reference, SourceRunner):
            self.reference = reference
            self._owns_reference = False
        else:
            self.reference = SourceRunner(reference, language=reference_lang)
            self._owns_reference = True

        # Wrap generator
        if isinstance(generator, str):
            # Template string
            rng = RandomGenerator()
            template_str = generator
            self.generator_fn: Callable[[], str] = lambda: rng.from_template(template_str)
        elif isinstance(generator, RandomGenerator):
            self.generator_fn = lambda: generator.from_template("n=int(1,10); a=array(n, 1, 100)")
        elif callable(generator):
            self.generator_fn = generator
        else:
            raise TypeError(f"Invalid generator type: {type(generator)}")

        self.comparator = comparator or OutputComparator()
        self.minimizer = minimizer or DeltaDebugger(comparator=self.comparator)

    def fuzz(
        self,
        max_runs: int = 100,
        timeout_sec: float = 2.0,
        stop_on_first_fail: bool = True,
        minimize: bool = True,
        compare_mode: str = "tokens",  # "tokens", "exact", "float"
        eps: float = 1e-6,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> FuzzReport:
        """Run differential fuzzing loop.

        Args:
            max_runs: Number of testcases to generate and evaluate.
            timeout_sec: Per-testcase time limit.
            stop_on_first_fail: Stop upon detecting first counterexample.
            minimize: Minimize failing counterexample with DeltaDebugger.
            compare_mode: 'tokens' (default), 'exact', or 'float'.
            eps: Epsilon tolerance for float comparison.
            progress_callback: Optional callback fn(current_run, max_runs).

        Returns:
            FuzzReport summarizing results and minimal counterexamples.
        """
        start_time = time.perf_counter()
        passed_runs = 0
        counterexamples: list[Counterexample] = []
        minimal_case: Optional[str] = None

        # Select comparison function
        if compare_mode == "exact":
            cmp_fn = self.comparator.compare_exact
        elif compare_mode == "float":
            cmp_fn = lambda e, a: self.comparator.compare_float(e, a, eps=eps)
        else:
            cmp_fn = self.comparator.compare_tokens

        for run_idx in range(1, max_runs + 1):
            if progress_callback:
                progress_callback(run_idx, max_runs)

            test_input = self.generator_fn()

            # Execute reference solution
            ref_res = self.reference.run(test_input, timeout_sec=timeout_sec)
            # Execute candidate solution
            cand_res = self.candidate.run(test_input, timeout_sec=timeout_sec)

            is_failing = False
            cmp_result = ComparisonResult(match=True)

            if cand_res.is_tle and not ref_res.is_tle:
                is_failing = True
                cmp_result = ComparisonResult(match=False, diff_details="Candidate timed out (TLE)")
            elif cand_res.is_rte and not ref_res.is_rte:
                is_failing = True
                cmp_result = ComparisonResult(match=False, diff_details=f"Candidate crashed (RTE): {cand_res.stderr}")
            elif not cand_res.is_ok and ref_res.is_ok:
                is_failing = True
                cmp_result = ComparisonResult(match=False, diff_details=f"Candidate failed with status {cand_res.status}")
            else:
                # Compare stdout outputs
                cmp_result = cmp_fn(ref_res.stdout, cand_res.stdout)
                if not cmp_result.match:
                    is_failing = True

            if is_failing:
                ce = Counterexample(
                    input_data=test_input,
                    candidate_result=cand_res,
                    reference_result=ref_res,
                    comparison=cmp_result,
                    run_index=run_idx,
                )
                counterexamples.append(ce)

                if minimize and minimal_case is None:
                    # Shrink the counterexample using DeltaDebugger
                    minimal_case = self.minimizer.minimize(
                        input_data=test_input,
                        candidate=self.candidate,
                        reference=self.reference,
                        timeout_sec=timeout_sec,
                    )

                if stop_on_first_fail:
                    break
            else:
                passed_runs += 1

        duration = time.perf_counter() - start_time
        total_executed = passed_runs + len(counterexamples)

        return FuzzReport(
            total_runs=total_executed,
            passed_runs=passed_runs,
            counterexamples_found=len(counterexamples),
            minimal_case=minimal_case,
            counterexamples=counterexamples,
            duration_sec=duration,
        )

    def close(self) -> None:
        """Clean up owned runners."""
        if self._owns_candidate:
            self.candidate.cleanup()
        if self._owns_reference:
            self.reference.cleanup()

    def __enter__(self) -> StressFuzzer:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def fuzz(
    candidate: Union[SourceRunner, str, Path],
    reference: Union[SourceRunner, str, Path],
    generator: Union[RandomGenerator, Callable[[], str], str],
    max_runs: int = 100,
    timeout_sec: float = 2.0,
    stop_on_first_fail: bool = True,
    minimize: bool = True,
    compare_mode: str = "tokens",
    eps: float = 1e-6,
) -> FuzzReport:
    """Convenience helper to run differential fuzzing in one line."""
    with StressFuzzer(candidate, reference, generator) as fuzzer:
        return fuzzer.fuzz(
            max_runs=max_runs,
            timeout_sec=timeout_sec,
            stop_on_first_fail=stop_on_first_fail,
            minimize=minimize,
            compare_mode=compare_mode,
            eps=eps,
        )

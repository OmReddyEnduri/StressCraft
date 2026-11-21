"""Tests for StressFuzzer and end-to-end differential fuzzing."""

import unittest
from stresscraft.fuzzer import StressFuzzer, fuzz
from stresscraft.models import Language
from stresscraft.runners import SourceRunner


class TestFuzzer(unittest.TestCase):
    def test_fuzzer_detects_wrong_answer_and_minimizes(self):
        # Reference solution: correct maximum of array
        # Candidate solution: buggy maximum (fails if any element > 40)
        ref_code = """
import sys
tokens = sys.stdin.read().split()
if tokens:
    n = int(tokens[0])
    arr = [int(x) for x in tokens[1:n+1]]
    print(max(arr))
"""

        cand_code = """
import sys
tokens = sys.stdin.read().split()
if tokens:
    n = int(tokens[0])
    arr = [int(x) for x in tokens[1:n+1]]
    # Bug: fails when element > 40
    res = max(arr)
    if res > 40:
        print(res + 1)  # Wrong answer!
    else:
        print(res)
"""
        template = "n=int(2, 6); a=array(n, 1, 100)"

        ref_runner = SourceRunner.from_code(ref_code, language=Language.PYTHON)
        cand_runner = SourceRunner.from_code(cand_code, language=Language.PYTHON)

        try:
            with StressFuzzer(
                candidate=cand_runner,
                reference=ref_runner,
                generator=template,
            ) as fuzzer:
                report = fuzzer.fuzz(max_runs=20, stop_on_first_fail=True, minimize=True)
                self.assertFalse(report.success)
                self.assertGreater(report.counterexamples_found, 0)
                self.assertIsNotNone(report.minimal_case)
                # The minimal case should have shrunk the input significantly
                min_lines = report.minimal_case.strip().split("\n")
                self.assertLessEqual(len(min_lines), 2)
        finally:
            ref_runner.cleanup()
            cand_runner.cleanup()


if __name__ == "__main__":
    unittest.main()

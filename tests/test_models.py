"""
Tests for stresscraft.models
"""

import unittest
from pathlib import Path

from stresscraft.models import (
    ComparisonResult,
    Counterexample,
    FuzzReport,
    Language,
    RunResult,
    RunStatus,
)


class TestModels(unittest.TestCase):
    def test_language_from_extension(self):
        self.assertEqual(Language.from_extension("solution.cpp"), Language.CPP)
        self.assertEqual(Language.from_extension("main.cc"), Language.CPP)
        self.assertEqual(Language.from_extension("test.cxx"), Language.CPP)
        self.assertEqual(Language.from_extension(Path("code.py")), Language.PYTHON)
        self.assertEqual(Language.from_extension("algo.rs"), Language.RUST)
        self.assertEqual(Language.from_extension("server.go"), Language.GO)
        self.assertEqual(Language.from_extension("Main.java"), Language.JAVA)

        with self.assertRaises(ValueError):
            Language.from_extension("unknown.xyz")

    def test_language_from_string(self):
        self.assertEqual(Language.from_string("cpp"), Language.CPP)
        self.assertEqual(Language.from_string("C++"), Language.CPP)
        self.assertEqual(Language.from_string("G++"), Language.CPP)
        self.assertEqual(Language.from_string("python"), Language.PYTHON)
        self.assertEqual(Language.from_string("py"), Language.PYTHON)
        self.assertEqual(Language.from_string("rust"), Language.RUST)
        self.assertEqual(Language.from_string("rs"), Language.RUST)
        self.assertEqual(Language.from_string("go"), Language.GO)
        self.assertEqual(Language.from_string("golang"), Language.GO)
        self.assertEqual(Language.from_string("java"), Language.JAVA)

        with self.assertRaises(ValueError):
            Language.from_string("unsupported_lang")

    def test_run_status(self):
        self.assertEqual(RunStatus.OK.value, "OK")
        self.assertEqual(RunStatus.TLE.value, "TLE")
        self.assertEqual(RunStatus.MLE.value, "MLE")
        self.assertEqual(RunStatus.RTE.value, "RTE")
        self.assertEqual(RunStatus.CE.value, "CE")

    def test_run_result_properties(self):
        ok_res = RunResult(status=RunStatus.OK, exit_code=0)
        self.assertTrue(ok_res.is_ok)
        self.assertFalse(ok_res.is_tle)
        self.assertFalse(ok_res.is_rte)
        self.assertFalse(ok_res.is_ce)

        tle_res = RunResult(status=RunStatus.TLE, exit_code=-1)
        self.assertFalse(tle_res.is_ok)
        self.assertTrue(tle_res.is_tle)

        rte_res = RunResult(status=RunStatus.RTE, exit_code=1)
        self.assertFalse(rte_res.is_ok)
        self.assertTrue(rte_res.is_rte)

        ce_res = RunResult(status=RunStatus.CE, compilation_error="Syntax error")
        self.assertFalse(ce_res.is_ok)
        self.assertTrue(ce_res.is_ce)

    def test_comparison_result(self):
        cmp_true = ComparisonResult(match=True)
        self.assertTrue(bool(cmp_true))

        cmp_false = ComparisonResult(
            match=False,
            diff_details="Line mismatch",
            expected_token="10",
            actual_token="20",
            line_number=1,
            token_index=0,
        )
        self.assertFalse(bool(cmp_false))
        self.assertEqual(cmp_false.line_number, 1)
        self.assertEqual(cmp_false.token_index, 0)

    def test_counterexample_classification(self):
        tle_res = RunResult(status=RunStatus.TLE)
        ok_res = RunResult(status=RunStatus.OK, stdout="42")
        ce_tle = Counterexample("1\n", tle_res, ok_res, ComparisonResult(match=False))
        self.assertEqual(ce_tle.failure_type, "TLE")

        rte_res = RunResult(status=RunStatus.RTE, exit_code=139)
        ce_rte = Counterexample("1\n", rte_res, ok_res, ComparisonResult(match=False))
        self.assertEqual(ce_rte.failure_type, "RTE")

        wa_cand = RunResult(status=RunStatus.OK, stdout="100")
        ce_wa = Counterexample("1\n", wa_cand, ok_res, ComparisonResult(match=False))
        self.assertEqual(ce_wa.failure_type, "WA")

        ce_ok = Counterexample("1\n", ok_res, ok_res, ComparisonResult(match=True))
        self.assertEqual(ce_ok.failure_type, "UNKNOWN")

    def test_fuzz_report_summary(self):
        report_ok = FuzzReport(
            total_runs=100,
            passed_runs=100,
            counterexamples_found=0,
            duration_sec=1.5,
        )
        self.assertTrue(report_ok.success)
        summary_text = report_ok.summary()
        self.assertIn("ALL TESTS PASSED", summary_text)
        self.assertIn("Total Iterations:       100", summary_text)

        ok_res = RunResult(status=RunStatus.OK, stdout="10")
        wa_res = RunResult(status=RunStatus.OK, stdout="20")
        ce = Counterexample("test input", wa_res, ok_res, ComparisonResult(match=False, diff_details="diff"))
        report_fail = FuzzReport(
            total_runs=10,
            passed_runs=9,
            counterexamples_found=1,
            minimal_case="min input",
            counterexamples=[ce],
            duration_sec=0.5,
        )
        self.assertFalse(report_fail.success)
        fail_summary = report_fail.summary()
        self.assertIn("Counterexamples Found:  1", fail_summary)
        self.assertIn("Minimal Reproducible Counterexample:", fail_summary)
        self.assertIn("min input", fail_summary)


if __name__ == "__main__":
    unittest.main()

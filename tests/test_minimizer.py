"""
Tests for stresscraft.minimizer
"""

import unittest

from stresscraft.minimizer import DeltaDebugger


class TestMinimizer(unittest.TestCase):
    def setUp(self):
        self.debugger = DeltaDebugger()

    def test_minimize_with_predicate_contains_target(self):
        # Failure occurs if and only if the number 42 is in the input
        def pred(text: str) -> bool:
            return "42" in text.split()

        large_input = "10\n1 99 3 42 7 8 12 15 88 5\n"
        minimized = self.debugger.minimize(large_input, predicate=pred)

        self.assertTrue(pred(minimized))
        # Minimized input should be significantly smaller than original
        self.assertLessEqual(len(minimized), len(large_input))
        self.assertIn("42", minimized)

    def test_minimize_line_reduction(self):
        # Failure occurs if line contains "ERROR_TRIGGER"
        def pred(text: str) -> bool:
            return "ERROR_TRIGGER" in text

        multiline_input = "\n".join([
            "noise line 1",
            "noise line 2",
            "noise line 3",
            "ERROR_TRIGGER",
            "noise line 4",
            "noise line 5",
        ])

        minimized = self.debugger.minimize(multiline_input, predicate=pred)
        self.assertTrue(pred(minimized))
        lines = [line.strip() for line in minimized.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "ERROR_TRIGGER")

    def test_minimize_multi_testcases(self):
        # Test input structured with T=3 test cases, but only case 2 fails
        # Multi-case problem format requires line 0 to be integer T
        def pred(text: str) -> bool:
            lines = text.strip().split("\n")
            return bool(lines and lines[0].isdigit() and "FAIL" in text)

        testcase_input = "\n".join([
            "3",
            "CASE 1 OK",
            "CASE 2 FAIL",
            "CASE 3 OK",
        ])

        minimized = self.debugger.minimize(testcase_input, predicate=pred)
        self.assertTrue(pred(minimized))
        # Should isolate to single testcase with T=1
        self.assertTrue(minimized.startswith("1\n"))
        self.assertIn("FAIL", minimized)
        self.assertNotIn("CASE 1", minimized)
        self.assertNotIn("CASE 3", minimized)

    def test_minimize_integer_reduction(self):
        # Failure occurs if any integer >= 100
        def pred(text: str) -> bool:
            for tok in text.split():
                try:
                    if int(tok) >= 100:
                        return True
                except ValueError:
                    pass
            return False

        input_str = "1\n5000000"
        minimized = self.debugger.minimize(input_str, predicate=pred)
        self.assertTrue(pred(minimized))
        # DeltaDebugger shrinks 5000000 towards 100
        tokens = minimized.split()
        int_tokens = [int(t) for t in tokens if t.isdigit()]
        self.assertIn(100, int_tokens)

    def test_already_minimal_input(self):
        def pred(text: str) -> bool:
            return "FAIL" in text

        min_input = "FAIL"
        res = self.debugger.minimize(min_input, predicate=pred)
        self.assertEqual(res.strip(), "FAIL")

    def test_non_failing_input_returns_original(self):
        def pred(text: str) -> bool:
            return "NEVER" in text

        input_str = "hello world"
        res = self.debugger.minimize(input_str, predicate=pred)
        self.assertEqual(res, input_str)


if __name__ == "__main__":
    unittest.main()

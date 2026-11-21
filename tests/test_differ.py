"""
Tests for stresscraft.differ
"""

import unittest

from stresscraft.differ import OutputComparator


class TestDiffer(unittest.TestCase):
    def setUp(self):
        self.differ = OutputComparator()

    def test_compare_exact_identical(self):
        exp = "Hello World\nLine 2\n"
        act = "Hello World\r\nLine 2   \n"
        res = self.differ.compare_exact(exp, act)
        self.assertTrue(res.match)
        self.assertTrue(bool(res))

    def test_compare_exact_mismatch_line(self):
        exp = "1 2 3\n4 5 6\n7 8 9"
        act = "1 2 3\n4 99 6\n7 8 9"
        res = self.differ.compare_exact(exp, act)
        self.assertFalse(res.match)
        self.assertEqual(res.line_number, 2)
        self.assertEqual(res.expected_token, "4 5 6")
        self.assertEqual(res.actual_token, "4 99 6")

    def test_compare_exact_eof_mismatch(self):
        exp = "Line 1\nLine 2"
        act = "Line 1"
        res = self.differ.compare_exact(exp, act)
        self.assertFalse(res.match)
        self.assertEqual(res.line_number, 2)
        self.assertEqual(res.expected_token, "Line 2")
        self.assertEqual(res.actual_token, "<EOF>")

        # Extra line in actual
        res2 = self.differ.compare_exact("Line 1", "Line 1\nLine 2")
        self.assertFalse(res2.match)
        self.assertEqual(res2.expected_token, "<EOF>")
        self.assertEqual(res2.actual_token, "Line 2")

    def test_compare_tokens_equivalence(self):
        # Spacing and newline differences are ignored
        exp = "1   2   3\n4\n5 6"
        act = "1 2\n3 4 5\n\n6"
        res = self.differ.compare_tokens(exp, act)
        self.assertTrue(res.match)

    def test_compare_tokens_mismatch(self):
        exp = "1 2 3 4 5"
        act = "1 2 99 4 5"
        res = self.differ.compare_tokens(exp, act)
        self.assertFalse(res.match)
        self.assertEqual(res.token_index, 2)
        self.assertEqual(res.expected_token, "3")
        self.assertEqual(res.actual_token, "99")

    def test_compare_tokens_length_mismatch(self):
        exp = "1 2 3 4"
        act = "1 2"
        res = self.differ.compare_tokens(exp, act)
        self.assertFalse(res.match)
        self.assertEqual(res.token_index, 2)
        self.assertEqual(res.expected_token, "3")

        # Actual has extra
        res2 = self.differ.compare_tokens("1 2", "1 2 3")
        self.assertFalse(res2.match)
        self.assertEqual(res2.token_index, 2)
        self.assertEqual(res2.actual_token, "3")

    def test_compare_float_tolerance(self):
        # Within epsilon 1e-6
        exp = "3.1415926535 2.71828"
        act = "3.1415926540 2.71828"
        res = self.differ.compare_float(exp, act, eps=1e-6)
        self.assertTrue(res.match)

        # Exceeds epsilon
        act_bad = "3.14169 2.71828"
        res_bad = self.differ.compare_float(exp, act_bad, eps=1e-6)
        self.assertFalse(res_bad.match)
        self.assertEqual(res_bad.token_index, 0)
        self.assertIn("Float difference exceeded tolerance", res_bad.diff_details)

    def test_compare_float_non_numeric_fallback(self):
        exp = "YES 3.14 NO"
        act = "YES 3.14 NO"
        res = self.differ.compare_float(exp, act)
        self.assertTrue(res.match)

        act_diff = "YES 3.14 MAYBE"
        res_diff = self.differ.compare_float(exp, act_diff)
        self.assertFalse(res_diff.match)
        self.assertEqual(res_diff.token_index, 2)
        self.assertEqual(res_diff.expected_token, "NO")
        self.assertEqual(res_diff.actual_token, "MAYBE")

    def test_compare_float_nan_inf(self):
        exp = "nan inf -inf"
        act = "nan inf -inf"
        res = self.differ.compare_float(exp, act)
        self.assertTrue(res.match)


if __name__ == "__main__":
    unittest.main()

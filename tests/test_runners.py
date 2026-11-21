"""
Tests for stresscraft.runners
"""

import sys
import unittest
from pathlib import Path

from stresscraft.models import Language, RunStatus
from stresscraft.runners import SourceRunner


class TestRunners(unittest.TestCase):
    def test_python_inline_success(self):
        code = (
            "import sys\n"
            "data = sys.stdin.read().strip()\n"
            "print(f'OUTPUT: {data.upper()}')\n"
        )
        with SourceRunner.from_code(code, language=Language.PYTHON) as runner:
            res = runner.run("hello competitive programming")
            self.assertTrue(res.is_ok)
            self.assertEqual(res.exit_code, 0)
            self.assertEqual(res.status, RunStatus.OK)
            self.assertEqual(res.stdout.strip(), "OUTPUT: HELLO COMPETITIVE PROGRAMMING")
            self.assertGreater(res.time_ms, 0.0)

    def test_python_runtime_error(self):
        code = (
            "import sys\n"
            "sys.stderr.write('fatal crash occurred\\n')\n"
            "sys.exit(42)\n"
        )
        with SourceRunner.from_code(code, language=Language.PYTHON) as runner:
            res = runner.run("sample")
            self.assertFalse(res.is_ok)
            self.assertTrue(res.is_rte)
            self.assertEqual(res.exit_code, 42)
            self.assertEqual(res.status, RunStatus.RTE)
            self.assertIn("fatal crash occurred", res.stderr)

    def test_python_timeout_tle(self):
        code = (
            "import time\n"
            "time.sleep(5)\n"
            "print('done')\n"
        )
        with SourceRunner.from_code(code, language=Language.PYTHON) as runner:
            res = runner.run("", timeout_sec=0.3)
            self.assertFalse(res.is_ok)
            self.assertTrue(res.is_tle)
            self.assertEqual(res.status, RunStatus.TLE)
            self.assertIn("Execution Timed Out", res.stderr)

    def test_missing_source_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            SourceRunner("non_existent_file_path_12345.cpp")


if __name__ == "__main__":
    unittest.main()

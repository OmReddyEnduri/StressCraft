"""
Tests for stresscraft.cli
"""

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stresscraft.cli import create_parser, main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.parser = create_parser()
        self.temp_dir = tempfile.TemporaryDirectory(prefix="stresscraft_cli_test_")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parser_subcommands(self):
        args_fuzz = self.parser.parse_args(["fuzz", "sol.cpp", "ref.cpp", "-n", "50", "--timeout", "1.5"])
        self.assertEqual(args_fuzz.command, "fuzz")
        self.assertEqual(args_fuzz.candidate, "sol.cpp")
        self.assertEqual(args_fuzz.reference, "ref.cpp")
        self.assertEqual(args_fuzz.iterations, 50)
        self.assertEqual(args_fuzz.timeout, 1.5)

        args_gen = self.parser.parse_args(["gen", "--type", "array", "-n", "20", "--sorted"])
        self.assertEqual(args_gen.command, "gen")
        self.assertEqual(args_gen.type, "array")
        self.assertEqual(args_gen.size, 20)
        self.assertTrue(args_gen.sorted)

        args_min = self.parser.parse_args(["minimize", "-i", "in.txt", "-c", "c.py", "-r", "r.py"])
        self.assertEqual(args_min.command, "minimize")
        self.assertEqual(args_min.input, "in.txt")

        args_bench = self.parser.parse_args(["bench", "sol.py", "-s", "10,100", "-r", "2"])
        self.assertEqual(args_bench.command, "bench")
        self.assertEqual(args_bench.scales, "10,100")

    def test_cli_help_and_empty(self):
        # Empty args returns 0 and prints help
        ret = main([])
        self.assertEqual(ret, 0)

    def test_cli_gen_command(self):
        # Test generation with stdout capture
        out_buf = io.StringIO()
        with patch("sys.stdout", out_buf):
            ret = main(["gen", "--type", "array", "-n", "5", "--min-val", "10", "--max-val", "10", "--seed", "123"])
            self.assertEqual(ret, 0)

        output = out_buf.getvalue().strip()
        lines = output.splitlines()
        self.assertEqual(lines[0], "5")
        self.assertEqual(lines[1], "10 10 10 10 10")

    def test_cli_gen_to_file(self):
        out_file = Path(self.temp_dir.name) / "test_out.txt"
        ret = main(["gen", "-t", "n=3; a=array(n, 1, 1)", "-o", str(out_file)])
        self.assertEqual(ret, 0)
        self.assertTrue(out_file.exists())
        content = out_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(content[0], "3")
        self.assertEqual(content[1], "1 1 1")

    def test_cli_fuzz_success(self):
        # Create identical candidate and reference scripts
        cand_file = Path(self.temp_dir.name) / "cand.py"
        ref_file = Path(self.temp_dir.name) / "ref.py"

        code = (
            "import sys\n"
            "line = sys.stdin.read().strip()\n"
            "print(line)\n"
        )
        cand_file.write_text(code, encoding="utf-8")
        ref_file.write_text(code, encoding="utf-8")

        ret = main([
            "fuzz",
            str(cand_file),
            str(ref_file),
            "-n", "5",
            "-t", "a=array(3, 1, 10)",
            "--timeout", "2.0",
        ])
        self.assertEqual(ret, 0)

    def test_cli_fuzz_failure_detected_and_minimized(self):
        cand_file = Path(self.temp_dir.name) / "cand_buggy.py"
        ref_file = Path(self.temp_dir.name) / "ref_correct.py"
        out_min_file = Path(self.temp_dir.name) / "counterexample.txt"

        # Reference calculates sum of array
        ref_code = (
            "import sys\n"
            "tokens = sys.stdin.read().split()\n"
            "if tokens:\n"
            "    n = int(tokens[0])\n"
            "    arr = [int(x) for x in tokens[1:1+n]]\n"
            "    print(sum(arr))\n"
        )
        # Buggy candidate fails if any element > 50
        cand_code = (
            "import sys\n"
            "tokens = sys.stdin.read().split()\n"
            "if tokens:\n"
            "    n = int(tokens[0])\n"
            "    arr = [int(x) for x in tokens[1:1+n]]\n"
            "    if any(x > 50 for x in arr):\n"
            "        print(-1)\n"
            "    else:\n"
            "        print(sum(arr))\n"
        )

        ref_file.write_text(ref_code, encoding="utf-8")
        cand_file.write_text(cand_code, encoding="utf-8")

        ret = main([
            "fuzz",
            str(cand_file),
            str(ref_file),
            "-n", "20",
            "-t", "n=int(3, 6); a=array(n, 40, 100)",
            "-o", str(out_min_file),
            "--timeout", "2.0",
        ])
        # Returns 1 when counterexample is discovered
        self.assertEqual(ret, 1)
        self.assertTrue(out_min_file.exists())
        self.assertGreater(len(out_min_file.read_text(encoding="utf-8")), 0)

    def test_cli_bench(self):
        sol_file = Path(self.temp_dir.name) / "sol.py"
        code = (
            "import sys\n"
            "data = sys.stdin.read().split()\n"
            "if data:\n"
            "    print(len(data))\n"
        )
        sol_file.write_text(code, encoding="utf-8")

        ret = main([
            "bench",
            str(sol_file),
            "-s", "10,50",
            "-r", "2",
            "-t", "n={N}; a=array(n, 1, 10)",
            "--timeout", "2.0",
        ])
        self.assertEqual(ret, 0)

    def test_cli_minimize_command(self):
        cand_file = Path(self.temp_dir.name) / "cand_min.py"
        ref_file = Path(self.temp_dir.name) / "ref_min.py"
        in_file = Path(self.temp_dir.name) / "failing_input.txt"
        out_file = Path(self.temp_dir.name) / "shrunken.txt"

        cand_file.write_text("import sys\nprint('FAIL' if '42' in sys.stdin.read() else 'OK')\n", encoding="utf-8")
        ref_file.write_text("import sys\nprint('OK')\n", encoding="utf-8")
        in_file.write_text("10\n1 2 3 42 5 6 7 8 9 10\n", encoding="utf-8")

        ret = main([
            "minimize",
            "-i", str(in_file),
            "-c", str(cand_file),
            "-r", str(ref_file),
            "-o", str(out_file),
            "--timeout", "2.0",
        ])
        self.assertEqual(ret, 0)
        self.assertTrue(out_file.exists())
        shrunken = out_file.read_text(encoding="utf-8")
        self.assertIn("42", shrunken)


if __name__ == "__main__":
    unittest.main()

# StressCraft ⚡

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests: 100% Pass](https://img.shields.io/badge/Tests-100%25%20Passing-brightgreen.svg)]()
[![Platform: Cross-Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)]()

> **High-performance automated competitive programming differential fuzzing, testcase generator, and delta-debugging counterexample minimizer engine.**

---

## 🎯 Motivation

In competitive programming (Codeforces, AtCoder, LeetCode, ICPC), finding why a solution gets **Wrong Answer (WA)**, **Time Limit Exceeded (TLE)**, or **Runtime Error (RTE)** is notoriously frustrating. Typical manual stress testing relies on fragile bash or Python loops that spit out 10,000-line test cases that are impossible to manually trace.

**StressCraft** replaces hacky scripts with an industrial-grade differential testing harness:
1. **Automated Differential Fuzzing**: Concurrently pits your candidate solution against a naive brute-force or reference solution.
2. **CP-Specific Template DSL**: Expressively generates complex arrays, permutations, uniformly random Cayley trees (via Prüfer sequences), connected/weighted graphs, 2D grids, and strings.
3. **Hierarchical Delta-Debugging (`ddmin`)**: Automatically shrinks massive failing test cases down to the **minimal reproducible counterexample** (e.g., shrinking $N=100,000$ down to $N=3$).
4. **Asymptotic Complexity Profiler**: Benchmarks runtime and memory scaling from $N=10$ to $N=100,000+$ to catch asymptotic bottlenecks before submission.
5. **Interactive Rich CLI**: Colorized failure panels, live execution progress, token diffs, and execution telemetry.

---

## 🏗️ Architecture & Workflow

```text
 ┌────────────────────────────────────────────────────────┐
 │                   Competitive Problem                  │
 └───────────────────────────┬────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
   ┌──────────────────────┐      ┌──────────────────────┐
   │  Candidate Solution  │      │  Reference Solution  │
   │   (Fast / Complex)   │      │ (Brute-Force / Model)│
   └──────────┬───────────┘      └──────────┬───────────┘
              │                             │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │   StressCraft Fuzz Engine   │ ◄── [Template DSL / RandomGenerator]
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │      Output Comparator      │
              │  (Tokens / Exact / Floats)  │
              └──────────────┬──────────────┘
                             │
                  [Difference Detected?]
                             │
              ┌──────────────┴──────────────┐
           No │                          Yes│
              ▼                             ▼
   ┌──────────────────────┐      ┌──────────────────────┐
   │  ✔ All Tests Passed  │      │ Delta-Debug Minimizer│
   │  Ready for Submit!   │      └──────────┬───────────┘
   └──────────────────────┘                 │
                                            ▼
                                 ┌──────────────────────┐
                                 │ Minimal Countercase  │
                                 │ (e.g., N=3, K=1)     │
                                 └──────────────────────┘
```

---

## ✨ Key Features

- **Multi-Language Engine**: First-class compilation and execution for **C++** (`g++`/`clang++`), **Python**, **Rust**, **Go**, and **Java** with automated clean process-tree termination.
- **Microsecond Precision & Telemetry**: Accurately measures CPU runtime, exit codes, and peak resident memory set.
- **CP-Native Random Generators**:
  - **Cayley Trees**: Uniformly distributed tree topologies generated using Prüfer sequence decoders with randomized vertex labeling.
  - **Connected & Weighted Graphs**: Spanning tree initialization with rejection-sampled edges to guarantee connectivity and prevent self-loops/parallel edges.
  - **Permutations & Arrays**: Custom ranges, strict distinct element enforcement, and sorted ordering options.
  - **2D Grids & Strings**: Custom matrix dimensions and character alphabets.
- **Smart Output Differ**:
  - `tokens`: Whitespace/newline-invariant token comparison.
  - `exact`: Line-by-line whitespace-normalized diffing with exact line and column tracking.
  - `float`: Token-by-token comparison supporting absolute and relative tolerance ($\epsilon = 10^{-6}$).
- **Delta-Debugging (`ddmin`)**: Multi-phase reduction passes (multi-testcase decomposition, line trimming, array shrinking with header count synchronization, integer binary-search reduction towards 0 or 1, and string simplification).
- **Asymptotic Profiling (`bench`)**: Stress test candidates across user-defined scaling milestones ($N=10, 100, \dots, 10^5$) to identify $O(N^2)$ vs $O(N \log N)$ thresholds.

---

## 📦 Installation

### From Source
```bash
git clone https://github.com/OmReddyEnduri/StressCraft.git
cd StressCraft
pip install .
```

### Development Installation
```bash
pip install -e ".[dev]"
```

Verify installation:
```bash
stresscraft --version
```

---

## 🚀 CLI Command Reference

### 1. `stresscraft fuzz`
Runs differential fuzzing between candidate file and reference file.

```bash
stresscraft fuzz <candidate> <reference> [options]
```

**Options:**
- `-g, -t, --template`: Template DSL expression (default: `'n=int(1,10); a=array(n, 1, 100)'`)
- `--gen-file`: Path to external generator script or template file
- `-n, --iterations`: Total test iterations to run (default: `100`)
- `--timeout`: Timeout per testcase in seconds (default: `2.0`)
- `-c, --compare`: Comparison mode: `tokens` (default), `exact`, `float`
- `--eps`: Tolerance for float comparison (default: `1e-6`)
- `--no-minimize`: Skip delta-debugging counterexample minimization
- `--keep-going`: Continue running tests even after finding a failure
- `-o, --output`: Save minimal failing testcase to a file

**Example:**
```bash
stresscraft fuzz solution.cpp brute.py -t "n=int(3,10); a=array(n, 1, 1000)" -n 200 -o counterexample.txt
```

---

### 2. `stresscraft minimize`
Takes a large failing testcase and shrinks it down to the minimal counterexample.

```bash
stresscraft minimize -i <failing_input> -c <candidate> -r <reference> [options]
```

**Options:**
- `-i, --input`: Path to file with failing testcase, or inline string
- `-c, --candidate`: Candidate solution file path
- `-r, --reference`: Reference solution file path
- `--timeout`: Per-run timeout in seconds (default: `2.0`)
- `-o, --output`: Output file to write minimized testcase

**Example:**
```bash
stresscraft minimize -i big_fail.in -c solve.cpp -r brute.py -o minimal.in
```

---

### 3. `stresscraft gen`
Generates randomized competitive programming testcases directly to stdout or a file.

```bash
stresscraft gen [options]
```

**Options:**
- `-t, --template`: Template DSL expression
- `--type`: Data structure type: `array`, `permutation`, `tree`, `graph`, `string`, `grid`, `int`
- `-n, --size`: Size $N$ (default: `10`)
- `--min-val, --max-val`: Minimum and maximum values
- `--sorted`: Sort generated array
- `--distinct`: Generate strictly unique elements
- `--directed`: Directed graph flag
- `--weighted`: Weighted graph flag
- `-m, --edges`: Edge count for graph
- `--rows, --cols`: Matrix dimensions for grid
- `--alphabet`: Alphabet for string generation
- `--seed`: Random seed for deterministic reproducibility
- `-c, --count`: Number of testcases to produce (default: `1`)
- `-o, --output`: Output file path (default: stdout)

**Examples:**
```bash
# Generate a random tree with 10 vertices
stresscraft gen --type tree -n 10

# Generate a sorted array of 8 distinct numbers between 1 and 100
stresscraft gen --type array -n 8 --min-val 1 --max-val 100 --sorted --distinct

# Generate complex CP testcase via template DSL
stresscraft gen -t "n=int(5,10); a=array(n, 1, 100); tree(n)"
```

---

### 4. `stresscraft bench`
Profiles runtime and memory across scale ($N=10$ to $N=100,000$) to find asymptotic bottlenecks.

```bash
stresscraft bench <solution> [options]
```

**Options:**
- `-s, --scales`: Comma-separated scale milestones (default: `'10,100,1000,10000,100000'`)
- `-t, --template`: Template pattern with `{N}` scale placeholder (default: `'n={N}; a=array(n, 1, 1000000)'`)
- `-r, --runs`: Runs per scale milestone to average (default: `3`)
- `--timeout`: Timeout limit in seconds (default: `10.0`)

**Example:**
```bash
stresscraft bench solution.cpp -s "100,1000,10000,100000" -t "n={N}; a=array(n, 1, 1000000)"
```

---

## 📝 Template DSL Specification

StressCraft features a safe Python-syntax AST DSL for writing testcase generators in one line.

| Construct | Description | Output Format |
|---|---|---|
| `int(min, max)` | Uniform random integer in $[min, max]$ | Space-separated number |
| `array(n, min, max, sorted=False, distinct=False)` | Random integer array of size $n$ | Space-separated list |
| `permutation(n, one_indexed=True)` | Random permutation of $1..n$ (or $0..n-1$) | Space-separated list |
| `string(length, alphabet="...")` | Random string of given length | String on its own line |
| `tree(n, one_indexed=True)` | Uniform Cayley tree with $n-1$ edges | $n-1$ lines of `u v` |
| `graph(n, m, directed=False, weighted=False)` | Connected simple graph with $m$ edges | $m$ lines of `u v [w]` |
| `grid(rows, cols, min=0, max=1)` | 2D matrix of random numbers | `rows` lines of space-separated values |
| `_var = expr` | Silent variable assignment (not printed) | Suppressed from output |
| `var = expr` | Variable assignment (printed to output) | Value printed to output |

### Example Templates:

**Graph Problem with Node and Edge Counts:**
```text
n=int(5, 10); m=int(n-1, n*2); graph(n, m, weighted=True, min_w=1, max_w=50)
```

**Multi-Testcase Problem ($T$ testcases):**
```text
t=3; a=array(5, 1, 10); b=array(5, 1, 10); c=array(5, 1, 10)
```

---

## 🐍 Python API Usage

You can also use StressCraft directly within your Python scripts or test harnesses:

```python
from stresscraft import fuzz, RandomGenerator, DeltaDebugger, SourceRunner

# 1. One-line differential fuzzing
report = fuzz(
    candidate="solution.cpp",
    reference="brute.py",
    generator="n=int(3, 10); a=array(n, 1, 100)",
    max_runs=100,
    timeout_sec=2.0,
)

if not report.success:
    print(f"Failed! Minimal counterexample:\n{report.minimal_case}")

# 2. Programmatic testcase generation
rng = RandomGenerator(seed=42)
testcase = rng.from_template("n=int(5, 10); a=permutation(n); tree(n)")
print(testcase)

# 3. Delta-debugging minimization
debugger = DeltaDebugger()
minimal = debugger.minimize(
    input_data="10\n1 99 3 42 7 8 12 15 88 5",
    predicate=lambda s: "42" in s.split(),
)
print(f"Minimal: {minimal}")
```

---

## 🧪 Testing & Verification

StressCraft includes a comprehensive unit test suite covering 100% of the core models, generators, diffing logic, delta-debugger, runners, and CLI commands.

Run tests using Python's standard `unittest`:
```bash
python -m unittest discover tests -v
```

Or using `pytest`:
```bash
pytest -v
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
Author: **Om Reddy Enduri** (<omreddyenduri@gmail.com>).

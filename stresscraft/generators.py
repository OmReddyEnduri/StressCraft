"""
StressCraft Generators
======================
High-performance random testcase generators and template DSL parser
for Competitive Programming data structures (integers, arrays, trees,
graphs, grids, strings, permutations).
"""

from __future__ import annotations

import ast
import heapq
import random
from typing import Any, Callable, Optional, Sequence, Union


class RandomGenerator:
    """Random testcase generator with CP-specific primitives and template DSL."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)

    def seed(self, seed: int) -> None:
        """Seed the underlying random number generator."""
        self._rng.seed(seed)

    def integer(self, min_val: int, max_val: int) -> int:
        """Generate a random integer uniformly distributed in [min_val, max_val]."""
        if min_val > max_val:
            min_val, max_val = max_val, min_val
        return self._rng.randint(min_val, max_val)

    def array(
        self,
        size: int,
        min_val: int,
        max_val: int,
        sorted: bool = False,
        distinct: bool = False,
    ) -> list[int]:
        """Generate a list of random integers.

        Args:
            size: Number of elements.
            min_val: Minimum integer value.
            max_val: Maximum integer value.
            sorted: Whether to sort elements in ascending order.
            distinct: Whether all elements must be strictly unique.
        """
        if size < 0:
            raise ValueError(f"Size must be non-negative, got {size}")
        if size == 0:
            return []
        if min_val > max_val:
            min_val, max_val = max_val, min_val

        range_size = max_val - min_val + 1
        if distinct:
            if size > range_size:
                raise ValueError(
                    f"Cannot generate {size} distinct elements in range [{min_val}, {max_val}]"
                )
            if range_size <= 10_000_000:
                result = self._rng.sample(range(min_val, max_val + 1), size)
            else:
                seen = set()
                result = []
                while len(result) < size:
                    val = self._rng.randint(min_val, max_val)
                    if val not in seen:
                        seen.add(val)
                        result.append(val)
        else:
            result = [self._rng.randint(min_val, max_val) for _ in range(size)]

        if sorted:
            result.sort()
        return result

    def permutation(self, n: int, one_indexed: bool = True) -> list[int]:
        """Generate a random permutation of integers from 1..n (or 0..n-1)."""
        if n < 0:
            raise ValueError(f"n must be non-negative, got {n}")
        if n == 0:
            return []
        start = 1 if one_indexed else 0
        p = list(range(start, start + n))
        self._rng.shuffle(p)
        return p

    def string(
        self,
        length: int,
        alphabet: str = "abcdefghijklmnopqrstuvwxyz",
    ) -> str:
        """Generate a random string of given length using characters from alphabet."""
        if length < 0:
            raise ValueError(f"Length must be non-negative, got {length}")
        if length == 0:
            return ""
        if not alphabet:
            raise ValueError("Alphabet cannot be empty")
        return "".join(self._rng.choices(alphabet, k=length))

    def tree(self, n: int, one_indexed: bool = True) -> list[tuple[int, int]]:
        """Generate a random valid tree with n vertices using Prüfer sequences.

        Generates a uniformly distributed random labeled tree (Cayley's theorem).
        Returns a list of (u, v) edge tuples.
        """
        if n <= 1:
            return []
        if n == 2:
            return [(1, 2)] if one_indexed else [(0, 1)]

        # Generate a uniform Prüfer sequence of length n - 2
        prufer = [self._rng.randint(0, n - 1) for _ in range(n - 2)]
        degree = [1] * n
        for node in prufer:
            degree[node] += 1

        leaf_heap = [i for i, deg in enumerate(degree) if deg == 1]
        heapq.heapify(leaf_heap)

        edges: list[tuple[int, int]] = []
        for node in prufer:
            leaf = heapq.heappop(leaf_heap)
            edges.append((leaf, node))
            degree[node] -= 1
            if degree[node] == 1:
                heapq.heappush(leaf_heap, node)

        u = heapq.heappop(leaf_heap)
        v = heapq.heappop(leaf_heap)
        edges.append((u, v))

        # Permute vertex labels to remove Prüfer min-leaf bias
        perm = list(range(n))
        self._rng.shuffle(perm)

        result: list[tuple[int, int]] = []
        offset = 1 if one_indexed else 0
        for edge_u, edge_v in edges:
            pu = perm[edge_u] + offset
            pv = perm[edge_v] + offset
            if self._rng.choice([True, False]):
                result.append((pu, pv))
            else:
                result.append((pv, pu))

        self._rng.shuffle(result)
        return result

    def graph(
        self,
        n: int,
        m: int,
        directed: bool = False,
        weighted: bool = False,
        min_w: int = 1,
        max_w: int = 100,
        connected: bool = True,
        one_indexed: bool = True,
    ) -> list[tuple[int, int] | tuple[int, int, int]]:
        """Generate a random graph with n vertices and m edges.

        Args:
            n: Number of vertices.
            m: Number of edges.
            directed: Whether edges are directed.
            weighted: Whether edges have integer weights.
            min_w: Minimum edge weight.
            max_w: Maximum edge weight.
            connected: Ensure the graph is connected (requires m >= n - 1).
            one_indexed: Vertices numbered 1..n if True, else 0..n-1.
        """
        if n <= 0:
            return []
        if n == 1:
            if m > 0:
                raise ValueError("Simple graph with 1 vertex cannot have edges")
            return []

        max_edges = n * (n - 1) if directed else (n * (n - 1)) // 2
        if m > max_edges:
            raise ValueError(
                f"Simple {'directed' if directed else 'undirected'} graph with {n} nodes "
                f"can have at most {max_edges} edges, requested {m}"
            )

        if connected and m < n - 1:
            raise ValueError(
                f"Connected graph with {n} nodes requires at least {n - 1} edges, got {m}"
            )

        offset = 1 if one_indexed else 0
        edge_set: set[tuple[int, int]] = set()
        edges_list: list[tuple[int, int]] = []

        def add_edge(u: int, v: int) -> bool:
            if u == v:
                return False
            key = (u, v) if directed else (min(u, v), max(u, v))
            if key in edge_set:
                return False
            edge_set.add(key)
            edges_list.append((u, v))
            return True

        if connected:
            # Build a random spanning tree first to guarantee connectivity
            tree_edges = self.tree(n, one_indexed=False)
            for u, v in tree_edges:
                u_lbl = u + offset
                v_lbl = v + offset
                if directed and self._rng.choice([True, False]):
                    u_lbl, v_lbl = v_lbl, u_lbl
                add_edge(u_lbl, v_lbl)

        # Add remaining edges until reaching m
        attempts = 0
        max_attempts = max(10_000, m * 20)
        while len(edges_list) < m and attempts < max_attempts:
            attempts += 1
            u = self._rng.randint(offset, n - 1 + offset)
            v = self._rng.randint(offset, n - 1 + offset)
            add_edge(u, v)

        # If rejection sampling was slow in dense graphs, enumerate remaining pairs
        if len(edges_list) < m:
            remaining_pairs = []
            for u in range(offset, n + offset):
                for v in range(offset, n + offset):
                    if u == v:
                        continue
                    if not directed and u > v:
                        continue
                    key = (u, v) if directed else (min(u, v), max(u, v))
                    if key not in edge_set:
                        remaining_pairs.append((u, v))
            needed = m - len(edges_list)
            for u, v in self._rng.sample(remaining_pairs, needed):
                add_edge(u, v)

        self._rng.shuffle(edges_list)

        if weighted:
            weighted_edges: list[tuple[int, int, int]] = []
            for u, v in edges_list:
                w = self.integer(min_w, max_w)
                weighted_edges.append((u, v, w))
            return weighted_edges

        return edges_list

    def grid(
        self,
        rows: int,
        cols: int,
        min_val: int = 0,
        max_val: int = 1,
    ) -> list[list[int]]:
        """Generate a 2D grid matrix of size rows x cols with random integers."""
        if rows < 0 or cols < 0:
            raise ValueError(f"Rows and cols must be non-negative, got rows={rows}, cols={cols}")
        if rows == 0 or cols == 0:
            return []
        return [
            [self.integer(min_val, max_val) for _ in range(cols)]
            for _ in range(rows)
        ]

    def from_template(self, template_str: str) -> str:
        """Parse and execute a Competitive Programming testcase generation template.

        Example templates:
            - `n=int(1,10); a=array(n, 1, 100); tree(n)`
            - `t=1; n=int(3,6); a=permutation(n); grid(2, n, 0, 9)`

        Syntax rules:
            - Statements separated by semicolons (`;`) or newlines (`\\n`).
            - `var = expr`: evaluates expr and saves to variable `var`.
              Values of public variables (not starting with `_`) are formatted to output.
            - `expr`: evaluates expression and formats to output.
            - `_var = expr`: evaluates expr silently without writing to output.
        """
        evaluator = _TemplateEvaluator(self)
        return evaluator.evaluate(template_str)


class _TemplateEvaluator:
    """Safe AST-based template expression parser and formatter."""

    def __init__(self, generator: RandomGenerator) -> None:
        self.generator = generator
        self.env: dict[str, Any] = {
            # Core generators
            "int": generator.integer,
            "integer": generator.integer,
            "array": generator.array,
            "permutation": generator.permutation,
            "string": generator.string,
            "tree": generator.tree,
            "graph": generator.graph,
            "grid": generator.grid,
            # Helper utilities
            "choice": generator._rng.choice,
            "float": lambda a, b, d=4: round(generator._rng.uniform(a, b), d),
            "abs": abs,
            "min": min,
            "max": max,
            "len": len,
            "range": range,
        }

    def evaluate(self, template_str: str) -> str:
        """Parse template string and return formatted CP testcase input."""
        # Split on semicolon or newline, strip each statement to avoid IndentationError
        raw_lines = [stmt.strip() for stmt in template_str.replace(";", "\n").split("\n")]
        normalized = "\n".join(line for line in raw_lines if line)
        if not normalized:
            return ""

        try:
            tree = ast.parse(normalized, mode="exec")
        except SyntaxError as e:
            raise ValueError(f"Invalid template syntax: {e}") from e

        output_lines: list[str] = []

        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                val = self._eval_expr(stmt.value)
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
                        self.env[var_name] = val
                        # Auto-output unless private (prefixed with underscore)
                        if not var_name.startswith("_"):
                            self._append_formatted(output_lines, val)
            elif isinstance(stmt, ast.Expr):
                val = self._eval_expr(stmt.value)
                self._append_formatted(output_lines, val)
            else:
                raise ValueError(f"Unsupported template statement: {ast.dump(stmt)}")

        return "\n".join(output_lines)

    def _eval_expr(self, node: ast.AST) -> Any:
        """Evaluate an AST expression node securely."""
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id in self.env:
                return self.env[node.id]
            raise NameError(f"Undefined template variable or function '{node.id}'")

        if isinstance(node, ast.Call):
            func = self._eval_expr(node.func)
            args = [self._eval_expr(a) for a in node.args]
            kwargs = {kw.arg: self._eval_expr(kw.value) for kw in node.keywords if kw.arg}
            return func(*args, **kwargs)

        if isinstance(node, ast.UnaryOp):
            val = self._eval_expr(node.operand)
            if isinstance(node.op, ast.USub):
                return -val
            if isinstance(node.op, ast.UAdd):
                return +val
            if isinstance(node.op, ast.Not):
                return not val

        if isinstance(node, ast.BinOp):
            left = self._eval_expr(node.left)
            right = self._eval_expr(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Mod):
                return left % right
            if isinstance(node.op, ast.Pow):
                return left ** right

        if isinstance(node, ast.List):
            return [self._eval_expr(elt) for elt in node.elts]

        if isinstance(node, ast.Tuple):
            return tuple(self._eval_expr(elt) for elt in node.elts)

        if isinstance(node, ast.Subscript):
            val = self._eval_expr(node.value)
            idx = self._eval_expr(node.slice)
            return val[idx]

        raise ValueError(f"Unsupported AST expression: {ast.dump(node)}")

    def _append_formatted(self, output_lines: list[str], val: Any) -> None:
        """Format Python values into standard CP space/newline separated strings."""
        if val is None:
            return

        if isinstance(val, (int, float)):
            output_lines.append(str(val))
        elif isinstance(val, str):
            output_lines.append(val)
        elif isinstance(val, tuple):
            output_lines.append(" ".join(str(x) for x in val))
        elif isinstance(val, list):
            if not val:
                return
            first = val[0]
            if isinstance(first, tuple):
                # E.g. tree/graph edges -> each edge on its own line
                for edge in val:
                    output_lines.append(" ".join(str(x) for x in edge))
            elif isinstance(first, list):
                # E.g. 2D grid matrix -> each row on its own line
                for row in val:
                    output_lines.append(" ".join(str(x) for x in row))
            else:
                # E.g. array or permutation -> space separated numbers on one line
                output_lines.append(" ".join(str(x) for x in val))
        else:
            output_lines.append(str(val))

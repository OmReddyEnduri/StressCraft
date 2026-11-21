"""
Tests for stresscraft.generators
"""

import unittest
from collections import defaultdict, deque

from stresscraft.generators import RandomGenerator


class TestGenerators(unittest.TestCase):
    def setUp(self):
        self.rng = RandomGenerator(seed=42)

    def test_seed_determinism(self):
        rng1 = RandomGenerator(seed=12345)
        rng2 = RandomGenerator(seed=12345)
        self.assertEqual(rng1.array(10, 1, 100), rng2.array(10, 1, 100))
        self.assertEqual(rng1.string(20), rng2.string(20))

    def test_integer(self):
        val = self.rng.integer(10, 20)
        self.assertGreaterEqual(val, 10)
        self.assertLessEqual(val, 20)

        # Inverted bounds
        val_inv = self.rng.integer(50, 30)
        self.assertGreaterEqual(val_inv, 30)
        self.assertLessEqual(val_inv, 50)

    def test_array_bounds_and_properties(self):
        # Empty array
        self.assertEqual(self.rng.array(0, 1, 10), [])

        # Negative size raises ValueError
        with self.assertRaises(ValueError):
            self.rng.array(-5, 1, 10)

        # Bounds check
        arr = self.rng.array(100, 15, 25)
        self.assertEqual(len(arr), 100)
        for x in arr:
            self.assertGreaterEqual(x, 15)
            self.assertLessEqual(x, 25)

        # Sorted array
        sorted_arr = self.rng.array(50, -100, 100, sorted=True)
        self.assertEqual(len(sorted_arr), 50)
        self.assertEqual(sorted_arr, sorted(sorted_arr))

        # Distinct array
        distinct_arr = self.rng.array(30, 1, 50, distinct=True)
        self.assertEqual(len(distinct_arr), 30)
        self.assertEqual(len(set(distinct_arr)), 30)

        # Distinct with impossible bounds raises ValueError
        with self.assertRaises(ValueError):
            self.rng.array(20, 1, 10, distinct=True)

    def test_permutation(self):
        perm_1 = self.rng.permutation(10, one_indexed=True)
        self.assertEqual(len(perm_1), 10)
        self.assertEqual(sorted(perm_1), list(range(1, 11)))

        perm_0 = self.rng.permutation(10, one_indexed=False)
        self.assertEqual(len(perm_0), 10)
        self.assertEqual(sorted(perm_0), list(range(0, 10)))

        self.assertEqual(self.rng.permutation(0), [])
        with self.assertRaises(ValueError):
            self.rng.permutation(-1)

    def test_string(self):
        s = self.rng.string(50, alphabet="ACGT")
        self.assertEqual(len(s), 50)
        for char in s:
            self.assertIn(char, "ACGT")

        self.assertEqual(self.rng.string(0), "")
        with self.assertRaises(ValueError):
            self.rng.string(-3)
        with self.assertRaises(ValueError):
            self.rng.string(10, alphabet="")

    def test_tree_acyclicity_and_connectivity(self):
        n = 20
        edges = self.rng.tree(n, one_indexed=True)
        # Tree with n vertices must have exactly n - 1 edges
        self.assertEqual(len(edges), n - 1)

        # Verify connectivity and acyclicity using BFS
        adj = defaultdict(list)
        for u, v in edges:
            self.assertGreaterEqual(u, 1)
            self.assertLessEqual(u, n)
            self.assertGreaterEqual(v, 1)
            self.assertLessEqual(v, n)
            self.assertNotEqual(u, v)
            adj[u].append(v)
            adj[v].append(u)

        visited = set()
        queue = deque([1])
        visited.add(1)

        while queue:
            curr = queue.popleft()
            for neighbor in adj[curr]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        # All n vertices reached -> connected and acyclic
        self.assertEqual(len(visited), n)

        # Small tree base cases
        self.assertEqual(self.rng.tree(0), [])
        self.assertEqual(self.rng.tree(1), [])
        self.assertEqual(len(self.rng.tree(2)), 1)

    def test_graph_properties(self):
        n = 10
        m = 15
        edges = self.rng.graph(n, m, directed=False, connected=True, one_indexed=True)
        self.assertEqual(len(edges), m)

        # Simple graph verification: no self loops, no duplicates
        edge_set = set()
        adj = defaultdict(list)
        for u, v in edges:
            self.assertNotEqual(u, v)
            canonical = (min(u, v), max(u, v))
            self.assertNotIn(canonical, edge_set)
            edge_set.add(canonical)
            adj[u].append(v)
            adj[v].append(u)

        # Verify connectivity
        visited = set()
        queue = deque([1])
        visited.add(1)
        while queue:
            curr = queue.popleft()
            for neighbor in adj[curr]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        self.assertEqual(len(visited), n)

        # Weighted graph
        w_edges = self.rng.graph(5, 7, weighted=True, min_w=10, max_w=50)
        self.assertEqual(len(w_edges), 7)
        for edge in w_edges:
            self.assertEqual(len(edge), 3)
            u, v, w = edge
            self.assertGreaterEqual(w, 10)
            self.assertLessEqual(w, 50)

        # Error cases
        with self.assertRaises(ValueError):
            # Graph too dense
            self.rng.graph(4, 10)
        with self.assertRaises(ValueError):
            # Connected graph with m < n - 1
            self.rng.graph(5, 2, connected=True)

    def test_grid(self):
        grid = self.rng.grid(3, 4, min_val=0, max_val=9)
        self.assertEqual(len(grid), 3)
        for row in grid:
            self.assertEqual(len(row), 4)
            for val in row:
                self.assertGreaterEqual(val, 0)
                self.assertLessEqual(val, 9)

        self.assertEqual(self.rng.grid(0, 5), [])

    def test_from_template(self):
        template = "n=5; a=array(n, 1, 10)"
        out = self.rng.from_template(template)
        lines = out.strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "5")
        arr_tokens = lines[1].split()
        self.assertEqual(len(arr_tokens), 5)

        # Silent private variable
        template_silent = "_n=3; a=array(_n, 7, 7)"
        out_silent = self.rng.from_template(template_silent)
        self.assertEqual(out_silent.strip(), "7 7 7")

        # Tree template
        template_tree = "n=4; tree(n)"
        out_tree = self.rng.from_template(template_tree)
        tree_lines = out_tree.strip().split("\n")
        self.assertEqual(len(tree_lines), 4)  # 1 for n=4, 3 for edges

        # Syntax error
        with self.assertRaises(ValueError):
            self.rng.from_template("invalid syntax %%% = =")


if __name__ == "__main__":
    unittest.main()

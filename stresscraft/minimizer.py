"""
StressCraft Delta Debugger & Minimizer
======================================
Hierarchical delta debugging (ddmin) engine tailored for Competitive Programming.
Shrinks failing testcases down to minimal reproducible counterexamples:
- Line-level minimization
- Array element trimming and length header synchronization
- Integer magnitude reduction towards 0, 1, or minimum bounds via binary search
- String shortening and character simplification
- Sound verification: every shrunken candidate is validated against the failure predicate.
"""

from __future__ import annotations

import re
from typing import Callable, Optional, Union

from stresscraft.differ import OutputComparator
from stresscraft.models import ComparisonResult, RunResult, RunStatus
from stresscraft.runners import SourceRunner


class DeltaDebugger:
    """Automated hierarchical testcase minimizer for Competitive Programming."""

    def __init__(
        self,
        predicate: Optional[Callable[[str], bool]] = None,
        comparator: Optional[OutputComparator] = None,
    ) -> None:
        self.predicate = predicate
        self.comparator = comparator or OutputComparator()

    def minimize(
        self,
        input_data: str,
        predicate: Optional[Callable[[str], bool]] = None,
        candidate: Optional[SourceRunner] = None,
        reference: Optional[SourceRunner] = None,
        timeout_sec: float = 2.0,
        max_iterations: int = 12,
    ) -> str:
        """Shrink a failing input string to a minimal reproducible counterexample.

        Args:
            input_data: The original failing testcase string.
            predicate: Optional custom predicate f(test_input) -> bool.
            candidate: Candidate runner if predicate not provided.
            reference: Reference (brute force) runner if predicate not provided.
            timeout_sec: Timeout for runner execution when using candidate/reference.
            max_iterations: Maximum hierarchical refinement rounds.

        Returns:
            Minimized reproducible testcase string.
        """
        # Build failure predicate if not provided
        test_pred = predicate or self.predicate
        if test_pred is None:
            if candidate is None or reference is None:
                raise ValueError("Must provide either a predicate or both candidate and reference runners")
            test_pred = self._build_runner_predicate(candidate, reference, timeout_sec)

        normalized = input_data.replace("\r\n", "\n").strip()
        if not normalized:
            return input_data

        # Verify initial input actually reproduces failure
        if not test_pred(normalized):
            # Try with trailing newline
            if test_pred(normalized + "\n"):
                normalized = normalized + "\n"
            else:
                return input_data

        current_best = normalized

        # Multi-pass hierarchical shrinking loop
        for iteration in range(max_iterations):
            prev_best = current_best

            # Pass 0: Multi-testcase decomposition (T test cases)
            current_best = self._shrink_multi_testcases(current_best, test_pred)

            # Pass 1: Line-level ddmin chunk removal
            current_best = self._shrink_lines(current_best, test_pred)

            # Pass 2: Array element trimming & header synchronization
            current_best = self._shrink_arrays(current_best, test_pred)

            # Pass 3: Integer reduction towards 0, 1, or minimum bounds
            current_best = self._shrink_integers(current_best, test_pred)

            # Pass 4: String length reduction and character simplification
            current_best = self._shrink_strings(current_best, test_pred)

            # Check for convergence
            if current_best == prev_best:
                break

        return current_best

    def _build_runner_predicate(
        self,
        candidate: SourceRunner,
        reference: SourceRunner,
        timeout_sec: float,
    ) -> Callable[[str], bool]:
        """Construct a failure detection predicate from candidate and reference runners."""
        def predicate(test_input: str) -> bool:
            cand_res = candidate.run(test_input, timeout_sec=timeout_sec)
            ref_res = reference.run(test_input, timeout_sec=timeout_sec)

            # 1. Candidate timed out while reference completed
            if cand_res.is_tle and not ref_res.is_tle:
                return True

            # 2. Candidate crashed with runtime error while reference didn't
            if cand_res.is_rte and not ref_res.is_rte:
                return True

            # 3. Output mismatch (Wrong Answer)
            if cand_res.is_ok and ref_res.is_ok:
                cmp = self.comparator.compare_tokens(ref_res.stdout, cand_res.stdout)
                return not cmp.match

            return False

        return predicate

    def _shrink_multi_testcases(self, text: str, pred: Callable[[str], bool]) -> str:
        """Check if input begins with T testcases; if so, test individual cases with T=1."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if len(lines) < 3:
            return text

        # Check if first line is a single integer T > 1
        first_tokens = lines[0].split()
        if len(first_tokens) != 1:
            return text

        try:
            t = int(first_tokens[0])
        except ValueError:
            return text

        if t <= 1:
            return text

        body_lines = lines[1:]
        # If body lines divide evenly by T, each testcase is (len // T) lines
        if len(body_lines) % t == 0:
            lines_per_case = len(body_lines) // t
            for case_idx in range(t):
                case_chunk = body_lines[case_idx * lines_per_case : (case_idx + 1) * lines_per_case]
                single_case_input = "1\n" + "\n".join(case_chunk)
                if pred(single_case_input):
                    return single_case_input

        return text

    def _shrink_lines(self, text: str, pred: Callable[[str], bool]) -> str:
        """Delta debugging chunk removal on lines."""
        lines = text.split("\n")
        if len(lines) <= 1:
            return text

        n = len(lines)
        granularity = 2

        # Header detection: does line 0 contain an integer indicating line count?
        while granularity <= n:
            chunk_size = max(1, n // granularity)
            reduced = False

            for i in range(0, n, chunk_size):
                # Try omitting slice [i, i + chunk_size]
                remaining = lines[:i] + lines[i + chunk_size :]
                if not remaining:
                    continue

                cand = "\n".join(remaining).strip()
                if cand and pred(cand):
                    lines = remaining
                    n = len(lines)
                    reduced = True
                    break

                # Also test if line 0 needs to be synced with remaining body lines
                if len(remaining) > 1 and i > 0:
                    first_toks = remaining[0].split()
                    if len(first_toks) == 1 and first_toks[0].isdigit():
                        synced_first = f"{len(remaining) - 1}"
                        synced_cand = "\n".join([synced_first, *remaining[1:]]).strip()
                        if pred(synced_cand):
                            lines = [synced_first, *remaining[1:]]
                            n = len(lines)
                            reduced = True
                            break

            if reduced:
                granularity = 2
            else:
                granularity *= 2

        return "\n".join(lines).strip()

    def _shrink_arrays(self, text: str, pred: Callable[[str], bool]) -> str:
        """Trim elements from array lines and synchronize length header tokens."""
        lines = text.split("\n")
        for line_idx, line in enumerate(lines):
            tokens = line.split()
            if len(tokens) <= 1:
                continue

            orig_len = len(tokens)
            # Try removing halves and subsets of tokens
            step = max(1, orig_len // 2)
            while step >= 1:
                # Try prefix of size orig_len - step
                for target_size in [1, 2, orig_len // 2, orig_len - step]:
                    if target_size <= 0 or target_size >= orig_len:
                        continue
                    new_tokens = tokens[:target_size]
                    if self._try_token_replacement(lines, line_idx, tokens, new_tokens, pred):
                        lines[line_idx] = " ".join(new_tokens)
                        tokens = new_tokens
                        orig_len = len(tokens)
                        break
                step //= 2

            # Try removing individual elements one-by-one from the right
            i = len(tokens) - 1
            while i >= 0 and len(tokens) > 1:
                new_tokens = tokens[:i] + tokens[i + 1 :]
                if self._try_token_replacement(lines, line_idx, tokens, new_tokens, pred):
                    lines[line_idx] = " ".join(new_tokens)
                    tokens = new_tokens
                    i = min(i, len(tokens) - 1)
                else:
                    i -= 1

        return "\n".join(lines).strip()

    def _try_token_replacement(
        self,
        lines: list[str],
        line_idx: int,
        orig_tokens: list[str],
        new_tokens: list[str],
        pred: Callable[[str], bool],
    ) -> bool:
        """Test candidate line replacement, syncing preceding length headers if present."""
        test_lines = list(lines)
        test_lines[line_idx] = " ".join(new_tokens)

        # 1. Try directly without header sync
        cand = "\n".join(test_lines).strip()
        if pred(cand):
            return True

        # 2. Try syncing length in preceding line (e.g. line_idx - 1 had 'len(orig_tokens)')
        if line_idx > 0:
            prev_line = test_lines[line_idx - 1]
            prev_toks = prev_line.split()
            synced = False
            for p_idx, tok in enumerate(prev_toks):
                if tok == str(len(orig_tokens)):
                    prev_toks[p_idx] = str(len(new_tokens))
                    synced = True
            if synced:
                test_lines[line_idx - 1] = " ".join(prev_toks)
                cand = "\n".join(test_lines).strip()
                if pred(cand):
                    lines[line_idx - 1] = test_lines[line_idx - 1]
                    return True

        return False

    def _shrink_integers(self, text: str, pred: Callable[[str], bool]) -> str:
        """Reduce integer magnitudes towards 0, 1, or minimum bounds using binary search."""
        lines = text.split("\n")

        for line_idx, line in enumerate(lines):
            tokens = line.split()
            line_changed = False

            for tok_idx, tok in enumerate(tokens):
                try:
                    val = int(tok)
                except ValueError:
                    continue

                if val in (0, 1):
                    continue

                # Target candidates in preference order
                targets = [0, 1] if val > 0 else [0, -1]

                reduced = False
                for target in targets:
                    new_toks = list(tokens)
                    new_toks[tok_idx] = str(target)
                    cand_lines = list(lines)
                    cand_lines[line_idx] = " ".join(new_toks)
                    if pred("\n".join(cand_lines).strip()):
                        val = target
                        tokens[tok_idx] = str(target)
                        lines[line_idx] = " ".join(tokens)
                        line_changed = True
                        reduced = True
                        break

                if not reduced:
                    # Binary search between target and val
                    low, high = (1, val) if val > 0 else (val, 0)
                    best_val = val

                    # Binary search for smaller magnitude
                    iterations = 0
                    while low < high and iterations < 20:
                        iterations += 1
                        mid = (low + high) // 2
                        new_toks = list(tokens)
                        new_toks[tok_idx] = str(mid)
                        cand_lines = list(lines)
                        cand_lines[line_idx] = " ".join(new_toks)
                        if pred("\n".join(cand_lines).strip()):
                            best_val = mid
                            high = mid  # Can we go even smaller?
                        else:
                            low = mid + 1

                    if best_val != val:
                        tokens[tok_idx] = str(best_val)
                        lines[line_idx] = " ".join(tokens)
                        line_changed = True

        return "\n".join(lines).strip()

    def _shrink_strings(self, text: str, pred: Callable[[str], bool]) -> str:
        """Shorten strings and simplify characters."""
        lines = text.split("\n")

        for line_idx, line in enumerate(lines):
            tokens = line.split()
            for tok_idx, tok in enumerate(tokens):
                # Only operate on non-numeric string tokens
                if tok.lstrip("-").isdigit():
                    continue

                # 1. Try shortening length
                if len(tok) > 1:
                    for target_len in [1, 2, len(tok) // 2]:
                        shortened = tok[:target_len]
                        new_toks = list(tokens)
                        new_toks[tok_idx] = shortened
                        cand_lines = list(lines)
                        cand_lines[line_idx] = " ".join(new_toks)
                        if pred("\n".join(cand_lines).strip()):
                            tok = shortened
                            tokens[tok_idx] = tok
                            lines[line_idx] = " ".join(tokens)
                            break

                # 2. Try character simplification (replace chars with 'a' or '0')
                if any(c != 'a' for c in tok):
                    all_a = "a" * len(tok)
                    new_toks = list(tokens)
                    new_toks[tok_idx] = all_a
                    cand_lines = list(lines)
                    cand_lines[line_idx] = " ".join(new_toks)
                    if pred("\n".join(cand_lines).strip()):
                        tokens[tok_idx] = all_a
                        lines[line_idx] = " ".join(tokens)

        return "\n".join(lines).strip()

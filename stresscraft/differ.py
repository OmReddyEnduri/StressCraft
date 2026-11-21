"""
StressCraft Output Differ
=========================
High-precision output diffing and verification for Competitive Programming.
Supports exact whitespace-normalized diff, tokenized comparison,
and token-by-token floating-point tolerance comparison.
"""

from __future__ import annotations

import difflib
import math
from typing import Optional

from stresscraft.models import ComparisonResult


class OutputComparator:
    """Compares expected (reference) and actual (candidate) outputs."""

    @staticmethod
    def compare_exact(expected: str, actual: str) -> ComparisonResult:
        """Normalized whitespace line-by-line comparison.

        Normalizes line endings (\\r\\n -> \\n), strips trailing whitespace per line,
        and removes trailing blank lines before matching.
        """
        norm_exp = [line.rstrip() for line in expected.replace("\r\n", "\n").rstrip().split("\n")]
        norm_act = [line.rstrip() for line in actual.replace("\r\n", "\n").rstrip().split("\n")]

        # Handle empty output cases
        if norm_exp == [""]:
            norm_exp = []
        if norm_act == [""]:
            norm_act = []

        if norm_exp == norm_act:
            return ComparisonResult(match=True)

        # Pinpoint first mismatched line
        min_len = min(len(norm_exp), len(norm_act))
        mismatch_line = None
        exp_line_str = None
        act_line_str = None

        for idx in range(min_len):
            if norm_exp[idx] != norm_act[idx]:
                mismatch_line = idx + 1
                exp_line_str = norm_exp[idx]
                act_line_str = norm_act[idx]
                break

        if mismatch_line is None:
            # One output has extra lines
            mismatch_line = min_len + 1
            if len(norm_exp) > min_len:
                exp_line_str = norm_exp[min_len]
                act_line_str = "<EOF>"
            else:
                exp_line_str = "<EOF>"
                act_line_str = norm_act[min_len]

        diff_snippet = (
            f"Exact mismatch at line {mismatch_line}:\n"
            f"  Expected: {repr(exp_line_str)}\n"
            f"  Actual:   {repr(act_line_str)}"
        )

        return ComparisonResult(
            match=False,
            diff_details=diff_snippet,
            expected_token=exp_line_str,
            actual_token=act_line_str,
            line_number=mismatch_line,
        )

    @staticmethod
    def compare_tokens(expected: str, actual: str) -> ComparisonResult:
        """Token-by-token comparison ignoring all whitespace and newline differences.

        Tokens are extracted via standard whitespace splitting.
        """
        exp_tokens = expected.split()
        act_tokens = actual.split()

        if exp_tokens == act_tokens:
            return ComparisonResult(match=True)

        min_len = min(len(exp_tokens), len(act_tokens))
        for idx in range(min_len):
            if exp_tokens[idx] != act_tokens[idx]:
                return ComparisonResult(
                    match=False,
                    diff_details=(
                        f"Token mismatch at index {idx}:\n"
                        f"  Expected: {repr(exp_tokens[idx])}\n"
                        f"  Actual:   {repr(act_tokens[idx])}"
                    ),
                    expected_token=exp_tokens[idx],
                    actual_token=act_tokens[idx],
                    token_index=idx,
                )

        # Length mismatch
        if len(exp_tokens) > len(act_tokens):
            missing_idx = len(act_tokens)
            return ComparisonResult(
                match=False,
                diff_details=(
                    f"Token count mismatch: expected {len(exp_tokens)} tokens, but actual output "
                    f"only produced {len(act_tokens)} tokens. Missing token {missing_idx}: {repr(exp_tokens[missing_idx])}"
                ),
                expected_token=exp_tokens[missing_idx],
                actual_token=None,
                token_index=missing_idx,
            )
        else:
            extra_idx = len(exp_tokens)
            return ComparisonResult(
                match=False,
                diff_details=(
                    f"Token count mismatch: expected {len(exp_tokens)} tokens, but actual output "
                    f"produced {len(act_tokens)} tokens. Unexpected extra token {extra_idx}: {repr(act_tokens[extra_idx])}"
                ),
                expected_token=None,
                actual_token=act_tokens[extra_idx],
                token_index=extra_idx,
            )

    @staticmethod
    def compare_float(expected: str, actual: str, eps: float = 1e-6) -> ComparisonResult:
        """Token-by-token comparison with absolute and relative floating-point tolerance.

        For each token:
        - If both tokens parse as floats, checks |exp - act| <= max(eps, eps * |exp|).
        - If either token is non-numeric, falls back to exact string equality.
        """
        exp_tokens = expected.split()
        act_tokens = actual.split()

        if len(exp_tokens) != len(act_tokens):
            return ComparisonResult(
                match=False,
                diff_details=(
                    f"Float comparison token count mismatch: expected {len(exp_tokens)} tokens, "
                    f"got {len(act_tokens)} tokens"
                ),
                expected_token=exp_tokens[min(len(exp_tokens), len(act_tokens))] if exp_tokens else None,
                actual_token=act_tokens[min(len(exp_tokens), len(act_tokens))] if act_tokens else None,
            )

        for idx, (exp_tok, act_tok) in enumerate(zip(exp_tokens, act_tokens)):
            # Try parsing as float
            exp_is_float = False
            act_is_float = False
            try:
                exp_val = float(exp_tok)
                exp_is_float = True
            except ValueError:
                exp_val = 0.0

            try:
                act_val = float(act_tok)
                act_is_float = True
            except ValueError:
                act_val = 0.0

            if exp_is_float and act_is_float:
                if math.isnan(exp_val) and math.isnan(act_val):
                    continue
                if math.isinf(exp_val) and math.isinf(act_val):
                    if (exp_val > 0) == (act_val > 0):
                        continue

                abs_diff = abs(exp_val - act_val)
                # Standard CP tolerance check: abs_diff <= eps OR relative_diff <= eps
                max_allowed = max(eps, eps * abs(exp_val))
                if abs_diff > max_allowed:
                    return ComparisonResult(
                        match=False,
                        diff_details=(
                            f"Float difference exceeded tolerance at token {idx}:\n"
                            f"  Expected: {exp_tok} ({exp_val})\n"
                            f"  Actual:   {act_tok} ({act_val})\n"
                            f"  Diff:     {abs_diff} (tolerance eps={eps})"
                        ),
                        expected_token=exp_tok,
                        actual_token=act_tok,
                        token_index=idx,
                    )
            else:
                # String comparison
                if exp_tok != act_tok:
                    return ComparisonResult(
                        match=False,
                        diff_details=(
                            f"Non-float token mismatch at index {idx}:\n"
                            f"  Expected: {repr(exp_tok)}\n"
                            f"  Actual:   {repr(act_tok)}"
                        ),
                        expected_token=exp_tok,
                        actual_token=act_tok,
                        token_index=idx,
                    )

        return ComparisonResult(match=True)

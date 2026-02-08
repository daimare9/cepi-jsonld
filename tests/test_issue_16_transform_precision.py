"""Tests for issue #16 — first_pipe_split IEEE 754 precision loss.

Verifies that pure-numeric strings with 16+ digits are preserved exactly,
avoiding the float intermediate that corrupts large identifiers.
"""

from __future__ import annotations

import pytest

from ceds_jsonld.transforms import first_pipe_split


class TestFirstPipeSplitPrecision:
    """IEEE 754 precision loss on 16+ digit numeric IDs."""

    def test_16_digit_number_preserved(self):
        """16-digit pure-numeric string must be preserved exactly."""
        assert first_pipe_split("9999999999999999") == "9999999999999999"

    def test_17_digit_number_preserved(self):
        """17-digit pure-numeric string must be preserved exactly."""
        assert first_pipe_split("12345678901234567") == "12345678901234567"

    def test_20_digit_number_preserved(self):
        """20-digit pure-numeric string must be preserved exactly."""
        assert first_pipe_split("98765432101234567890") == "98765432101234567890"

    def test_pipe_delimited_large_id(self):
        """First element of pipe-delimited value with large ID preserved."""
        assert first_pipe_split("9999999999999999|40420|6202378625") == "9999999999999999"

    def test_normal_float_artifact_still_cleaned(self):
        """Float artifacts like '989897099.0' are still cleaned to int."""
        assert first_pipe_split("989897099.0") == "989897099"

    def test_normal_pipe_split(self):
        """Standard pipe-delimited value still works."""
        assert first_pipe_split("989897099|40420|6202378625") == "989897099"

    def test_non_numeric_passthrough(self):
        """Non-numeric string passes through unchanged."""
        assert first_pipe_split("ABC-DEF|123") == "ABC-DEF"

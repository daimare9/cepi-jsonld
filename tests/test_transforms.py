"""Tests for built-in transform functions."""

from __future__ import annotations

import pytest

from ceds_jsonld.transforms import (
    BUILTIN_TRANSFORMS,
    date_format,
    first_pipe_split,
    get_transform,
    int_clean,
    race_prefix,
    sex_prefix,
)

# ---------------------------------------------------------------------------
# sex_prefix
# ---------------------------------------------------------------------------


class TestSexPrefix:
    def test_female(self):
        assert sex_prefix("Female") == "Sex_Female"

    def test_male(self):
        assert sex_prefix("Male") == "Sex_Male"

    def test_strips_whitespace(self):
        assert sex_prefix("  Female  ") == "Sex_Female"

    def test_preserves_case(self):
        assert sex_prefix("female") == "Sex_female"


# ---------------------------------------------------------------------------
# race_prefix
# ---------------------------------------------------------------------------


class TestRacePrefix:
    def test_simple_race(self):
        assert race_prefix("White") == "RaceAndEthnicity_White"

    def test_removes_spaces(self):
        assert race_prefix("American Indian Or Alaska Native") == "RaceAndEthnicity_AmericanIndianOrAlaskaNative"

    def test_strips_whitespace(self):
        assert race_prefix("  Black  ") == "RaceAndEthnicity_Black"


# ---------------------------------------------------------------------------
# first_pipe_split
# ---------------------------------------------------------------------------


class TestFirstPipeSplit:
    def test_multiple_values(self):
        assert first_pipe_split("989897099|40420|6202378625") == "989897099"

    def test_single_value(self):
        assert first_pipe_split("123456789") == "123456789"

    def test_cleans_float(self):
        assert first_pipe_split("989897099.0|40420") == "989897099"

    def test_non_numeric_passes_through(self):
        assert first_pipe_split("abc|def") == "abc"

    def test_infinity_passes_through(self):
        """Infinity must not raise OverflowError (issue #4)."""
        assert first_pipe_split("Infinity|123") == "Infinity"


# ---------------------------------------------------------------------------
# int_clean
# ---------------------------------------------------------------------------


class TestIntClean:
    def test_integer_string(self):
        assert int_clean("989897099") == "989897099"

    def test_float_string(self):
        assert int_clean("989897099.0") == "989897099"

    def test_non_numeric(self):
        assert int_clean("abc") == "abc"

    def test_zero(self):
        assert int_clean("0") == "0"

    def test_large_number(self):
        assert int_clean("6202378625.0") == "6202378625"

    def test_large_pure_integer_no_precision_loss(self):
        """100-digit pure-integer string must survive without mangling (issue #5)."""
        big = "9" * 100
        assert int_clean(big) == big

    def test_20_digit_id_preserved(self):
        """Long numeric identifiers (e.g. student IDs) must not lose digits."""
        long_id = "12345678901234567890"
        assert int_clean(long_id) == long_id

    def test_negative_large_integer(self):
        """Negative large integers should also be exact."""
        neg = "-" + "8" * 50
        assert int_clean(neg) == neg

    def test_large_float_string(self):
        """Float-like large numbers still go through the float path."""
        assert int_clean("12345678901234567.0") == str(int(float("12345678901234567.0")))

    def test_infinity_returns_passthrough(self):
        """Infinity must not raise OverflowError (issue #4)."""
        assert int_clean("Infinity") == "Infinity"

    def test_negative_infinity_returns_passthrough(self):
        """Negative infinity must not raise OverflowError (issue #4)."""
        assert int_clean("-Infinity") == "-Infinity"

    def test_nan_returns_passthrough(self):
        """NaN string should pass through unchanged."""
        assert int_clean("NaN") == "NaN"


# ---------------------------------------------------------------------------
# date_format
# ---------------------------------------------------------------------------


class TestDateFormat:
    def test_passthrough(self):
        assert date_format("1965-05-15") == "1965-05-15"

    def test_strips_whitespace(self):
        assert date_format("  1990-01-01  ") == "1990-01-01"


# ---------------------------------------------------------------------------
# Registry and get_transform
# ---------------------------------------------------------------------------


class TestTransformRegistry:
    def test_all_builtins_present(self):
        expected = {"sex_prefix", "race_prefix", "first_pipe_split", "int_clean", "date_format"}
        assert expected == set(BUILTIN_TRANSFORMS)

    def test_get_builtin(self):
        fn = get_transform("sex_prefix")
        assert fn("Female") == "Sex_Female"

    def test_get_custom_override(self):
        custom = {"my_transform": lambda v: v.upper()}
        fn = get_transform("my_transform", custom)
        assert fn("hello") == "HELLO"

    def test_missing_transform_raises(self):
        with pytest.raises(KeyError, match="no_such_transform"):
            get_transform("no_such_transform")

    def test_all_builtins_callable(self):
        for name, fn in BUILTIN_TRANSFORMS.items():
            assert callable(fn), f"Transform '{name}' is not callable"

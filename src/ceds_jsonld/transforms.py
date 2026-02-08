"""Built-in transform functions for field mapping.

Transforms convert raw source values into the format expected by JSON-LD output.
They are referenced by name in mapping YAML configs and applied by FieldMapper.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def sex_prefix(value: str) -> str:
    """Add 'Sex_' prefix to a sex/gender value.

    Args:
        value: Raw sex value, e.g. "Female", "Male".

    Returns:
        Prefixed value, e.g. "Sex_Female".
    """
    return f"Sex_{value.strip()}"


def race_prefix(value: str) -> str:
    """Add 'RaceAndEthnicity_' prefix to a race/ethnicity value.

    Args:
        value: Raw race value, e.g. "White", "Black", "American Indian Or Alaska Native".

    Returns:
        Prefixed value with spaces removed, e.g. "RaceAndEthnicity_White".
    """
    return f"RaceAndEthnicity_{value.strip().replace(' ', '')}"


def first_pipe_split(value: str) -> str:
    """Take the first value from a pipe-delimited string and clean numerics.

    Handles pandas float artifacts: "989897099.0" → "989897099".
    Pure-digit strings are converted via ``int()`` directly to avoid IEEE 754
    precision loss that would corrupt numbers with more than ~15 significant
    digits.

    Args:
        value: Pipe-delimited string, e.g. "989897099|40420|6202378625".

    Returns:
        First value, cleaned of numeric artifacts.
    """
    first = str(value).split("|")[0].strip()
    # Fast path for pure integers — avoids float() precision loss on large numbers.
    bare = first.lstrip("-")
    if bare.isdigit() and bare:
        return str(int(first))
    try:
        return str(int(float(first)))
    except (ValueError, TypeError, OverflowError):
        return first


def int_clean(value: str) -> str:
    """Clean numeric strings by removing float artifacts.

    Converts ``"989897099.0"`` → ``"989897099"``.  Non-numeric values pass
    through unchanged.  Pure-digit strings (with optional leading ``-``) are
    converted via ``int()`` directly to avoid IEEE 754 precision loss that
    would corrupt numbers with more than ~15 significant digits.

    Args:
        value: String that may represent a number.

    Returns:
        Cleaned string with integer representation if numeric.
    """
    s = str(value).strip()
    # Fast path for pure integers — avoids float() precision loss on large numbers.
    bare = s.lstrip("-")
    if bare.isdigit() and bare:
        return str(int(s))
    try:
        return str(int(float(s)))
    except (ValueError, TypeError, OverflowError):
        return s


def date_format(value: str) -> str:
    """Normalize a date string to ISO 8601 format (YYYY-MM-DD).

    Currently a pass-through; assumes input is already ISO formatted.

    Args:
        value: Date string.

    Returns:
        ISO 8601 date string.
    """
    return str(value).strip()


# ---------------------------------------------------------------------------
# Transform registry
# ---------------------------------------------------------------------------

BUILTIN_TRANSFORMS: dict[str, Callable[[str], str]] = {
    "sex_prefix": sex_prefix,
    "race_prefix": race_prefix,
    "first_pipe_split": first_pipe_split,
    "int_clean": int_clean,
    "date_format": date_format,
}


def get_transform(name: str, custom: dict[str, Callable[..., Any]] | None = None) -> Callable[..., Any]:
    """Look up a transform function by name.

    Args:
        name: The registered name of the transform.
        custom: Optional dict of user-registered transforms.

    Returns:
        The transform callable.

    Raises:
        KeyError: If the transform name is not found in builtins or custom.
    """
    if custom and name in custom:
        return custom[name]
    if name in BUILTIN_TRANSFORMS:
        return BUILTIN_TRANSFORMS[name]
    available = sorted({*BUILTIN_TRANSFORMS, *(custom or {})})
    msg = f"Unknown transform '{name}'. Available: {available}"
    raise KeyError(msg)

"""Built-in transform functions for field mapping.

Transforms convert raw source values into the format expected by JSON-LD output.
They are referenced by name in mapping YAML configs and applied by FieldMapper.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def sex_prefix(value: str) -> str | None:
    """Add 'Sex_' prefix to a sex/gender value.

    Args:
        value: Raw sex value, e.g. "Female", "Male".

    Returns:
        Prefixed value, e.g. "Sex_Female", or ``None`` if the
        input is empty or whitespace-only.
    """
    cleaned = value.strip()
    if not cleaned:
        return None
    return f"Sex_{cleaned}"


def race_prefix(value: str) -> str | None:
    """Add 'RaceAndEthnicity_' prefix to a race/ethnicity value.

    Args:
        value: Raw race value, e.g. "White", "Black", "American Indian Or Alaska Native".

    Returns:
        Prefixed value with spaces removed, e.g. "RaceAndEthnicity_White",
        or ``None`` if the input is empty or whitespace-only.
    """
    cleaned = value.strip().replace(' ', '')
    if not cleaned:
        return None
    return f"RaceAndEthnicity_{cleaned}"


def first_pipe_split(value: str) -> str | None:
    """Take the first value from a pipe-delimited string and clean numerics.

    Handles pandas float artifacts: "989897099.0" → "989897099".
    Pure-digit strings are converted via ``int()`` directly to avoid IEEE 754
    precision loss that would corrupt numbers with more than ~15 significant
    digits.

    Returns ``None`` when the input is empty or the first segment is
    empty/whitespace-only (e.g. a leading pipe ``"|12345"``).

    Args:
        value: Pipe-delimited string, e.g. "989897099|40420|6202378625".

    Returns:
        First value, cleaned of numeric artifacts, or ``None`` if empty.
    """
    first = str(value).split("|")[0].strip()
    if not first:
        return None
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
    """Normalize a date string to strict ISO 8601 date format (YYYY-MM-DD).

    Validation and normalisation rules:

    * Strips leading/trailing whitespace.
    * Strips time components from datetime strings (``2026-02-08T14:30:00`` → ``2026-02-08``).
    * Zero-pads unpadded dates (``2026-2-8`` → ``2026-02-08``).
    * Rejects non-date strings (``"yesterday"``, ``"02/08/2026"``).
    * Rejects impossible calendar dates (``9999-99-99``).

    Args:
        value: Date string.

    Returns:
        Strict ISO 8601 date string (``YYYY-MM-DD``).

    Raises:
        ValueError: If the value cannot be parsed as YYYY-MM-DD.
    """
    import datetime as _dt

    s = str(value).strip()

    # Strip time component if present (e.g. "2026-02-08T14:30:00")
    if "T" in s:
        s = s.split("T")[0]
    elif " " in s and "-" in s.split(" ")[0]:
        s = s.split(" ")[0]

    parts = s.split("-")
    if len(parts) != 3:
        msg = (
            f"Value '{value}' is not a valid ISO 8601 date. "
            f"Expected YYYY-MM-DD format (e.g. '2026-02-08')."
        )
        raise ValueError(msg)

    year_s, month_s, day_s = parts
    if not (year_s.isdigit() and month_s.isdigit() and day_s.isdigit()):
        msg = (
            f"Value '{value}' contains non-numeric date components. "
            f"Expected YYYY-MM-DD format (e.g. '2026-02-08')."
        )
        raise ValueError(msg)

    try:
        dt = _dt.date(int(year_s), int(month_s), int(day_s))
    except ValueError:
        msg = (
            f"Value '{value}' is not a valid calendar date. "
            f"Expected YYYY-MM-DD with valid month (1-12) and day."
        )
        raise ValueError(msg) from None

    return dt.isoformat()


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

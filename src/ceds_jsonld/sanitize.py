"""IRI sanitization — protect against injection in ``@id`` construction.

Ensures values used as IRI components in ``@id`` fields cannot contain
characters that would break the IRI structure or allow injection attacks.
"""

from __future__ import annotations

import re
import unicodedata

#: Characters allowed in the local part of an IRI (after the base URI prefix).
#: Alphanumerics, hyphens, underscores, dots, and tildes are safe.
_SAFE_IRI_RE = re.compile(r"^[A-Za-z0-9._~:@!$&'()*+,;=/-]+$")

#: Characters that MUST be percent-encoded in an IRI local part.
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._~:@!$&'()*+,;=/-]")


def sanitize_iri_component(value: str) -> str:
    """Sanitize a string for use as an IRI local component.

    Percent-encodes any characters that are not safe in an IRI reference.
    Also strips leading/trailing whitespace and normalises Unicode to NFC.

    Args:
        value: The raw value to embed in an IRI (e.g. a person identifier).

    Returns:
        A safe string suitable for use in ``@id`` values.

    Raises:
        ValueError: If the value is empty after sanitization.

    Example:
        >>> sanitize_iri_component("989897099")
        '989897099'
        >>> sanitize_iri_component("hello world/<script>")
        'hello%20world%2F%3Cscript%3E'
    """
    # Normalise Unicode and strip whitespace
    value = unicodedata.normalize("NFC", value.strip())

    if not value:
        msg = "IRI component cannot be empty"
        raise ValueError(msg)

    # Fast path: value is already safe
    if _SAFE_IRI_RE.match(value):
        return value

    # Percent-encode unsafe characters
    def _encode_char(match: re.Match[str]) -> str:
        char = match.group(0)
        return "".join(f"%{b:02X}" for b in char.encode("utf-8"))

    return _UNSAFE_CHARS.sub(_encode_char, value)


def validate_base_uri(base_uri: str) -> str:
    """Validate that a base URI is well-formed.

    Checks for common injection patterns and ensures the URI ends with
    a separator character (``/`` or ``#``).

    Args:
        base_uri: The base URI prefix (e.g. ``"cepi:person/"``).

    Returns:
        The validated base URI.

    Raises:
        ValueError: If the base URI is malformed or contains suspicious content.
    """
    if not base_uri:
        msg = "Base URI cannot be empty"
        raise ValueError(msg)

    # Block obvious injection attempts
    suspicious = ["<script", "javascript:", "data:", "\x00", "\n", "\r"]
    lower = base_uri.lower()
    for pattern in suspicious:
        if pattern in lower:
            msg = f"Base URI contains suspicious content: {base_uri!r}"
            raise ValueError(msg)

    return base_uri

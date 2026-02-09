"""Tests for URI handling fixes — issues #31 and #34.

#31: prepare_for_cosmos ignores ``#`` separator → wrong Cosmos id.
#34: validate_base_uri accepts whitespace, file://, percent-encoded traversal;
     validate_base_uri never called by Builder.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from ceds_jsonld.cosmos.prepare import prepare_for_cosmos
from ceds_jsonld.exceptions import BuildError, CosmosError
from ceds_jsonld.sanitize import validate_base_uri


# =====================================================================
# Issue #31 — prepare_for_cosmos hash separator
# =====================================================================


class TestCosmosHashSeparator:
    """Cosmos id extraction must handle ``#`` as a namespace separator."""

    def test_hash_only_separator(self) -> None:
        """``cepi:person#12345`` → id should be ``'12345'``."""
        doc: dict[str, Any] = {"@id": "cepi:person#12345", "@type": "Person"}
        result = prepare_for_cosmos(doc)
        assert result["id"] == "12345"

    def test_mixed_slash_and_hash(self) -> None:
        """``https://example.org/person#99`` → id should be ``'99'``."""
        doc: dict[str, Any] = {"@id": "https://example.org/person#99", "@type": "Person"}
        result = prepare_for_cosmos(doc)
        assert result["id"] == "99"

    def test_urn_with_hash(self) -> None:
        """``urn:ceds:person#ABC`` → id should be ``'ABC'``."""
        doc: dict[str, Any] = {"@id": "urn:ceds:person#ABC", "@type": "Person"}
        result = prepare_for_cosmos(doc)
        assert result["id"] == "ABC"

    def test_hash_at_end_raises(self) -> None:
        """URI ending with ``#`` yields empty id → must raise."""
        doc: dict[str, Any] = {"@id": "cepi:person#", "@type": "Person"}
        with pytest.raises(CosmosError, match="Cannot derive Cosmos 'id'"):
            prepare_for_cosmos(doc)

    def test_slash_separator_still_works(self) -> None:
        """Existing slash-based URIs must remain unaffected."""
        doc: dict[str, Any] = {"@id": "cepi:person/12345", "@type": "Person"}
        result = prepare_for_cosmos(doc)
        assert result["id"] == "12345"

    def test_no_separator_returns_whole_value(self) -> None:
        """Plain identifiers with no separator return the full value."""
        doc: dict[str, Any] = {"@id": "plain-id", "@type": "Person"}
        result = prepare_for_cosmos(doc)
        assert result["id"] == "plain-id"

    def test_multiple_hashes_uses_last(self) -> None:
        """``a#b#c`` → id should be ``'c'`` (last segment after #)."""
        doc: dict[str, Any] = {"@id": "a#b#c", "@type": "Person"}
        result = prepare_for_cosmos(doc)
        assert result["id"] == "c"

    def test_slash_then_hash(self) -> None:
        """``http://example.org/ns/person#42`` → id should be ``'42'``."""
        doc: dict[str, Any] = {"@id": "http://example.org/ns/person#42", "@type": "Person"}
        result = prepare_for_cosmos(doc)
        assert result["id"] == "42"


# =====================================================================
# Issue #34 — validate_base_uri gaps
# =====================================================================


class TestValidateBaseUriWhitespace:
    """Whitespace characters must be rejected in base URIs."""

    def test_embedded_space_rejected(self) -> None:
        with pytest.raises(ValueError, match="whitespace"):
            validate_base_uri("cepi:per son/")

    def test_embedded_tab_rejected(self) -> None:
        with pytest.raises(ValueError, match="whitespace"):
            validate_base_uri("cepi:person\t/")

    def test_embedded_vertical_tab_rejected(self) -> None:
        with pytest.raises(ValueError, match="whitespace"):
            validate_base_uri("cepi:person\x0b/")

    def test_embedded_form_feed_rejected(self) -> None:
        with pytest.raises(ValueError, match="whitespace"):
            validate_base_uri("cepi:person\x0c/")


class TestValidateBaseUriDangerousSchemes:
    """Dangerous URI schemes must be rejected."""

    def test_file_scheme_rejected(self) -> None:
        with pytest.raises(ValueError, match="disallowed scheme"):
            validate_base_uri("file:///etc/passwd#")

    def test_ftp_scheme_rejected(self) -> None:
        with pytest.raises(ValueError, match="disallowed scheme"):
            validate_base_uri("ftp://evil.example.com/")

    def test_file_scheme_uppercase_rejected(self) -> None:
        with pytest.raises(ValueError, match="disallowed scheme"):
            validate_base_uri("FILE:///etc/passwd#")

    def test_http_scheme_allowed(self) -> None:
        assert validate_base_uri("http://example.org/ns/") == "http://example.org/ns/"

    def test_https_scheme_allowed(self) -> None:
        assert validate_base_uri("https://example.org/ns#") == "https://example.org/ns#"


class TestValidateBaseUriEncodedTraversal:
    """Percent-encoded path traversal must be rejected."""

    def test_percent_encoded_dot_dot_slash(self) -> None:
        with pytest.raises(ValueError, match="percent-encoded path traversal"):
            validate_base_uri("cepi:%2E%2E/%2E%2E/etc/")

    def test_lowercase_percent_encoded(self) -> None:
        with pytest.raises(ValueError, match="percent-encoded path traversal"):
            validate_base_uri("cepi:%2e%2e/etc/")

    def test_mixed_case_percent_encoded(self) -> None:
        with pytest.raises(ValueError, match="percent-encoded path traversal"):
            validate_base_uri("cepi:%2E%2e/etc/")


class TestValidateBaseUriExistingChecksUnbroken:
    """Existing validation rules must still work after our changes."""

    def test_valid_slash_uri(self) -> None:
        assert validate_base_uri("cepi:person/") == "cepi:person/"

    def test_valid_hash_uri(self) -> None:
        assert validate_base_uri("http://example.org/ns#") == "http://example.org/ns#"

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_base_uri("")

    def test_script_injection_rejected(self) -> None:
        with pytest.raises(ValueError, match="suspicious"):
            validate_base_uri("<script>evil</script>")

    def test_javascript_scheme_rejected(self) -> None:
        with pytest.raises(ValueError, match="suspicious"):
            validate_base_uri("javascript:alert(1)")

    def test_null_byte_rejected(self) -> None:
        with pytest.raises(ValueError, match="suspicious"):
            validate_base_uri("cepi:person/\x00evil")

    def test_missing_trailing_separator_rejected(self) -> None:
        with pytest.raises(ValueError, match="must end with"):
            validate_base_uri("cepi:person")


# =====================================================================
# Issue #34 — validate_base_uri integration in Builder
# =====================================================================


class TestBuilderValidatesBaseUri:
    """JSONLDBuilder.__init__ must call validate_base_uri."""

    def _make_shape_def(self, base_uri: str) -> MagicMock:
        """Create a minimal mock ShapeDefinition."""
        shape_def = MagicMock()
        shape_def.name = "test-shape"
        shape_def.mapping_config = {
            "base_uri": base_uri,
            "type": "TestType",
            "context_url": "https://example.org/ctx",
            "properties": {},
        }
        shape_def.context = {}
        return shape_def

    def test_valid_base_uri_accepted(self) -> None:
        from ceds_jsonld.builder import JSONLDBuilder

        shape_def = self._make_shape_def("cepi:person/")
        # Should not raise
        builder = JSONLDBuilder(shape_def)
        assert builder is not None

    def test_whitespace_base_uri_rejected(self) -> None:
        from ceds_jsonld.builder import JSONLDBuilder

        shape_def = self._make_shape_def("cepi:per son/")
        with pytest.raises(BuildError, match="invalid base_uri"):
            JSONLDBuilder(shape_def)

    def test_file_scheme_base_uri_rejected(self) -> None:
        from ceds_jsonld.builder import JSONLDBuilder

        shape_def = self._make_shape_def("file:///etc/passwd#")
        with pytest.raises(BuildError, match="invalid base_uri"):
            JSONLDBuilder(shape_def)

    def test_missing_separator_base_uri_rejected(self) -> None:
        from ceds_jsonld.builder import JSONLDBuilder

        shape_def = self._make_shape_def("cepi:person")
        with pytest.raises(BuildError, match="invalid base_uri"):
            JSONLDBuilder(shape_def)

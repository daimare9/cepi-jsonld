"""Tests for issue #25 — serializer.dumps() must reject NaN/Infinity.

Root cause: stdlib json.dumps() defaults to allow_nan=True, producing bare
NaN/Infinity tokens that are invalid JSON per RFC 8259 and rejected by
JSON-LD processors and Cosmos DB.
"""

from __future__ import annotations

import pytest

from ceds_jsonld.exceptions import SerializationError
from ceds_jsonld.serializer import dumps, get_backend


class TestSerializerRejectsNonFiniteFloats:
    """dumps() must raise SerializationError for NaN/Infinity values."""

    def test_nan_raises(self) -> None:
        with pytest.raises((SerializationError, ValueError)):
            dumps({"x": float("nan")})

    def test_inf_raises(self) -> None:
        with pytest.raises((SerializationError, ValueError)):
            dumps({"x": float("inf")})

    def test_neg_inf_raises(self) -> None:
        with pytest.raises((SerializationError, ValueError)):
            dumps({"x": float("-inf")})

    def test_nan_in_nested_dict_raises(self) -> None:
        with pytest.raises((SerializationError, ValueError)):
            dumps({"a": {"b": float("nan")}})

    def test_nan_in_list_raises(self) -> None:
        with pytest.raises((SerializationError, ValueError)):
            dumps({"items": [1, 2, float("nan")]})

    def test_normal_float_succeeds(self) -> None:
        result = dumps({"x": 3.14})
        assert b"3.14" in result

    def test_zero_float_succeeds(self) -> None:
        result = dumps({"x": 0.0})
        assert b"0.0" in result

    def test_valid_json_ld_document_succeeds(self) -> None:
        """A typical JSON-LD document should serialize fine."""
        doc = {
            "@context": "https://example.org/context.json",
            "@id": "person:123",
            "@type": "Person",
            "hasPersonName": {
                "@type": "PersonName",
                "FirstName": "Jane",
                "LastOrSurname": "Doe",
            },
        }
        result = dumps(doc)
        assert b"Jane" in result
        assert b"Person" in result

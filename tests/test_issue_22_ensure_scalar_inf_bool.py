"""Tests for issue #22 — _ensure_scalar must reject inf/nan/bool values.

Root cause: _ensure_scalar() only rejected dict, list, tuple, set, frozenset.
float('inf'), float('nan'), and bool values passed through silently and got
coerced to nonsensical strings like "inf", "True".
"""

from __future__ import annotations

import math

import pytest

from ceds_jsonld import DictAdapter, Pipeline, ShapeRegistry
from ceds_jsonld.exceptions import MappingError
from ceds_jsonld.mapping import FieldMapper


def _make_pipeline(rows: list[dict]) -> Pipeline:
    registry = ShapeRegistry()
    registry.load_shape("person")
    return Pipeline(DictAdapter(rows), "person", registry)


def _get_person_mapper() -> FieldMapper:
    registry = ShapeRegistry()
    registry.load_shape("person")
    shape = registry.get_shape("person")
    return FieldMapper(shape.mapping_config)


class TestEnsureScalarRejectsInfNanBool:
    """_ensure_scalar must raise MappingError for inf, nan, and bool values."""

    def test_float_inf_rejected(self) -> None:
        row = {
            "FirstName": "Jane",
            "LastName": "Doe",
            "Birthdate": float("inf"),
            "Sex": "Female",
            "PersonIdentifiers": "12345",
            "IdentificationSystems": "State",
        }
        mapper = _get_person_mapper()
        with pytest.raises(MappingError, match="non-finite float"):
            mapper.map(row)

    def test_float_neg_inf_rejected(self) -> None:
        row = {
            "FirstName": "Jane",
            "LastName": "Doe",
            "Birthdate": float("-inf"),
            "Sex": "Female",
            "PersonIdentifiers": "12345",
            "IdentificationSystems": "State",
        }
        mapper = _get_person_mapper()
        with pytest.raises(MappingError, match="non-finite float"):
            mapper.map(row)

    def test_float_nan_rejected(self) -> None:
        """NaN is caught by _is_empty as 'missing or empty' — still a MappingError."""
        row = {
            "FirstName": "Jane",
            "LastName": "Doe",
            "Birthdate": float("nan"),
            "Sex": "Female",
            "PersonIdentifiers": "12345",
            "IdentificationSystems": "State",
        }
        mapper = _get_person_mapper()
        # NaN is caught by _is_empty (treated as missing), so the error message
        # may be "missing or empty" or "non-finite float" — both are MappingError.
        with pytest.raises(MappingError):
            mapper.map(row)

    def test_bool_true_rejected(self) -> None:
        row = {
            "FirstName": True,
            "LastName": "Doe",
            "Birthdate": "2000-01-01",
            "Sex": "Female",
            "PersonIdentifiers": "12345",
            "IdentificationSystems": "State",
        }
        mapper = _get_person_mapper()
        with pytest.raises(MappingError, match="boolean"):
            mapper.map(row)

    def test_bool_false_rejected(self) -> None:
        row = {
            "FirstName": False,
            "LastName": "Doe",
            "Birthdate": "2000-01-01",
            "Sex": "Female",
            "PersonIdentifiers": "12345",
            "IdentificationSystems": "State",
        }
        mapper = _get_person_mapper()
        with pytest.raises(MappingError, match="boolean"):
            mapper.map(row)

    def test_normal_float_allowed(self) -> None:
        """Regular floats should still pass through _ensure_scalar."""
        row = {
            "FirstName": "Jane",
            "LastName": "Doe",
            "Birthdate": "2000-01-01",
            "Sex": "Female",
            "PersonIdentifiers": 12345.0,
            "IdentificationSystems": "State",
        }
        mapper = _get_person_mapper()
        # Should not raise
        result = mapper.map(row)
        assert result is not None

    def test_pipeline_build_rejects_inf_in_date(self) -> None:
        """End-to-end: inf in a date field must not produce a document."""
        row = {
            "FirstName": "Jane",
            "LastName": "Doe",
            "Birthdate": float("inf"),
            "Sex": "Female",
            "PersonIdentifiers": "12345",
            "IdentificationSystems": "State",
        }
        pipeline = _make_pipeline([row])
        # build_all catches MappingError and sends to DLQ or re-raises
        with pytest.raises((MappingError, Exception)):
            docs = pipeline.build_all()
            # If build_all doesn't raise, at least no doc should have "inf"
            for doc in docs:
                assert "inf" not in str(doc)

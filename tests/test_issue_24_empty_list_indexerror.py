"""Tests for issue #24 — _build_sub_nodes IndexError on empty list values.

Root cause: The unwrap logic ``value if len(value) > 1 else value[0]`` crashes
when value is an empty list (len == 0 falls into else, value[0] on []).
"""

from __future__ import annotations

from ceds_jsonld import JSONLDBuilder, ShapeRegistry


def _get_builder() -> JSONLDBuilder:
    registry = ShapeRegistry()
    registry.load_shape("person")
    shape = registry.get_shape("person")
    return JSONLDBuilder(shape)


class TestBuildSubNodesEmptyList:
    """Empty list values must not crash the builder."""

    def test_empty_list_property_skipped(self) -> None:
        """An empty list at the property level should produce no output for that key."""
        builder = _get_builder()
        mapped_row = {
            "__id__": "person-1",
            "hasPersonName": [{"FirstName": "Jane", "LastOrSurname": "Doe"}],
            "hasPersonBirth": [{"Birthdate": "2000-01-01"}],
            "hasPersonSexGender": [{"hasSex": "Sex_Female"}],
            "hasPersonIdentifier": [],  # Empty list
        }
        doc = builder.build_one(mapped_row)
        # hasPersonIdentifier should be absent (skipped)
        assert "hasPersonIdentifier" not in doc

    def test_empty_list_field_value_no_crash(self) -> None:
        """An empty list as a field value within a sub-node must not crash."""
        builder = _get_builder()
        mapped_row = {
            "__id__": "person-2",
            "hasPersonName": [{"FirstName": "Jane", "LastOrSurname": "Doe"}],
            "hasPersonBirth": [{"Birthdate": "2000-01-01"}],
            "hasPersonSexGender": [{"hasSex": "Sex_Female"}],
            "hasPersonIdentifier": [
                {"PersonIdentifiers": [], "IdentificationSystems": "State"},
            ],
        }
        # Should not crash with IndexError
        doc = builder.build_one(mapped_row)
        assert doc is not None

    def test_single_element_list_unwrapped(self) -> None:
        """A single-element list should still be unwrapped to a scalar."""
        builder = _get_builder()
        mapped_row = {
            "__id__": "person-3",
            "hasPersonName": [{"FirstName": "Jane", "LastOrSurname": "Doe"}],
            "hasPersonBirth": [{"Birthdate": "2000-01-01"}],
            "hasPersonSexGender": [{"hasSex": "Sex_Female"}],
            "hasPersonIdentification": [
                {"PersonIdentifier": "12345", "hasPersonIdentificationSystem": "State"},
            ],
        }
        doc = builder.build_one(mapped_row)
        # Single instance should be unwrapped (not a list)
        assert isinstance(doc.get("hasPersonIdentification"), dict)

    def test_multi_element_list_kept_as_list(self) -> None:
        """Multiple instances should remain as a list."""
        builder = _get_builder()
        mapped_row = {
            "__id__": "person-4",
            "hasPersonName": [{"FirstName": "Jane", "LastOrSurname": "Doe"}],
            "hasPersonBirth": [{"Birthdate": "2000-01-01"}],
            "hasPersonSexGender": [{"hasSex": "Sex_Female"}],
            "hasPersonIdentification": [
                {"PersonIdentifier": "111", "hasPersonIdentificationSystem": "State"},
                {"PersonIdentifier": "222", "hasPersonIdentificationSystem": "District"},
            ],
        }
        doc = builder.build_one(mapped_row)
        assert isinstance(doc.get("hasPersonIdentification"), list)
        assert len(doc["hasPersonIdentification"]) == 2

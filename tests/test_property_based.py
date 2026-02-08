"""Property-based tests using Hypothesis.

Generates random but structurally valid data rows and verifies that the
pipeline maintains invariants regardless of input content.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ceds_jsonld.builder import JSONLDBuilder
from ceds_jsonld.mapping import FieldMapper
from ceds_jsonld.registry import ShapeRegistry
from ceds_jsonld.validator import PreBuildValidator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def person_artifacts():
    """Load Person shape artifacts once for the whole module."""
    registry = ShapeRegistry()
    shape_def = registry.load_shape("person")
    mapper = FieldMapper(shape_def.mapping_config)
    builder = JSONLDBuilder(shape_def)
    validator = PreBuildValidator(shape_def.mapping_config)
    return shape_def, mapper, builder, validator


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty text for required string fields
_name_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Date-like strings: YYYY-MM-DD
_date_text = st.dates().map(lambda d: d.isoformat())

# Sex values the transform expects
_sex_values = st.sampled_from(["Female", "Male"])

# Race values (can be comma-separated within pipe groups)
_single_race = st.sampled_from(
    [
        "White",
        "Black",
        "Asian",
        "AmericanIndianOrAlaskaNative",
        "HispanicOrLatinoEthnicity",
        "NativeHawaiianOrOtherPacificIslander",
    ]
)

_race_group = st.lists(_single_race, min_size=1, max_size=3).map(lambda ls: ",".join(ls))
_race_field = st.lists(_race_group, min_size=1, max_size=3).map(lambda gs: "|".join(gs))

# Identifiers (pipe-delimited)
_id_count = st.integers(min_value=1, max_value=4)
_single_id = st.integers(min_value=100000, max_value=999999999).map(str)

_id_system = st.sampled_from(
    [
        "PersonIdentificationSystem_SSN",
        "PersonIdentificationSystem_EducatorID",
        "PersonIdentificationSystem_State",
    ]
)

_id_type = st.sampled_from(
    [
        "PersonIdentifierType_PersonIdentifier",
        "PersonIdentifierType_StaffMemberIdentifier",
        "PersonIdentifierType_StudentIdentifier",
    ]
)


@st.composite
def person_row(draw):
    """Generate a random valid Person CSV row."""
    n = draw(st.integers(min_value=1, max_value=4))
    ids = draw(st.lists(_single_id, min_size=n, max_size=n))
    systems = draw(st.lists(_id_system, min_size=n, max_size=n))
    types = draw(st.lists(_id_type, min_size=n, max_size=n))

    return {
        "FirstName": draw(_name_text),
        "LastName": draw(_name_text),
        "Birthdate": draw(_date_text),
        "Sex": draw(_sex_values),
        "RaceEthnicity": draw(_race_field),
        "PersonIdentifiers": "|".join(ids),
        "IdentificationSystems": "|".join(systems),
        "PersonIdentifierTypes": "|".join(types),
    }


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------


class TestPropertyBased:
    """Invariants that must hold for any valid input row."""

    @given(row=person_row())
    @settings(max_examples=50, deadline=2000)
    def test_built_doc_always_has_required_keys(self, row, person_artifacts):
        """Every built document must contain @context, @type, @id."""
        _, mapper, builder, _ = person_artifacts
        mapped = mapper.map(row)
        doc = builder.build_one(mapped)

        assert "@context" in doc
        assert "@type" in doc
        assert "@id" in doc
        assert doc["@type"] == "Person"

    @given(row=person_row())
    @settings(max_examples=50, deadline=2000)
    def test_person_name_always_present(self, row, person_artifacts):
        """hasPersonName should always appear with FirstName and LastOrSurname."""
        _, mapper, builder, _ = person_artifacts
        mapped = mapper.map(row)
        doc = builder.build_one(mapped)

        assert "hasPersonName" in doc
        name = doc["hasPersonName"]
        assert "FirstName" in name
        assert "LastOrSurname" in name

    @given(row=person_row())
    @settings(max_examples=50, deadline=2000)
    def test_person_birth_always_present(self, row, person_artifacts):
        """hasPersonBirth should always appear with a Birthdate."""
        _, mapper, builder, _ = person_artifacts
        mapped = mapper.map(row)
        doc = builder.build_one(mapped)

        assert "hasPersonBirth" in doc
        birth = doc["hasPersonBirth"]
        assert "Birthdate" in birth

    @given(row=person_row())
    @settings(max_examples=50, deadline=2000)
    def test_id_is_non_empty_string(self, row, person_artifacts):
        """@id must be a non-empty string."""
        _, mapper, builder, _ = person_artifacts
        mapped = mapper.map(row)
        doc = builder.build_one(mapped)

        assert isinstance(doc["@id"], str)
        assert len(doc["@id"]) > 0

    @given(row=person_row())
    @settings(max_examples=50, deadline=2000)
    def test_pre_build_validator_accepts_valid_row(self, row, person_artifacts):
        """PreBuildValidator should accept every row we generate."""
        _, _, _, validator = person_artifacts
        result = validator.validate_row(row)
        assert result.conforms is True

    @given(row=person_row())
    @settings(max_examples=50, deadline=2000)
    def test_sub_shapes_have_type(self, row, person_artifacts):
        """Every sub-shape node must have an @type."""
        _, mapper, builder, _ = person_artifacts
        mapped = mapper.map(row)
        doc = builder.build_one(mapped)

        for key, value in doc.items():
            if key.startswith("@"):
                continue
            if isinstance(value, dict):
                assert "@type" in value, f"Sub-shape '{key}' missing @type"
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        assert "@type" in item, f"Sub-shape item in '{key}' missing @type"

    @given(row=person_row())
    @settings(max_examples=30, deadline=2000)
    def test_record_status_injected_in_sub_shapes(self, row, person_artifacts):
        """Sub-shapes with include_record_status should have hasRecordStatus."""
        _, mapper, builder, _ = person_artifacts
        mapped = mapper.map(row)
        doc = builder.build_one(mapped)

        for key in ("hasPersonName", "hasPersonBirth", "hasPersonSexGender"):
            if key in doc:
                node = doc[key]
                if isinstance(node, dict):
                    assert "hasRecordStatus" in node
                    assert "hasDataCollection" in node

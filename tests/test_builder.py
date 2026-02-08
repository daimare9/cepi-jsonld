"""Tests for JSONLDBuilder."""

from __future__ import annotations

import pytest

from ceds_jsonld.builder import JSONLDBuilder
from ceds_jsonld.exceptions import BuildError
from ceds_jsonld.mapping import FieldMapper


class TestBuildOneStructure:
    """Test top-level JSON-LD document structure."""

    def test_has_context(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        assert doc["@context"] == "https://cepi-dev.state.mi.us/ontology/context-person.json"

    def test_has_id(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        assert doc["@id"] == "cepi:person/989897099"

    def test_has_type(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        assert doc["@type"] == "Person"

    def test_has_all_properties(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        expected_props = {
            "hasPersonDemographicRace",
            "hasPersonIdentification",
            "hasPersonBirth",
            "hasPersonName",
            "hasPersonSexGender",
        }
        assert expected_props.issubset(set(doc))


class TestBuildOneSubShapes:
    """Test sub-shape construction and typed literals."""

    def test_person_name_fields(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        name = doc["hasPersonName"]
        assert name["@type"] == "PersonName"
        assert name["FirstName"] == "EDITH"
        assert name["LastOrSurname"] == "ADAMS"
        assert name["MiddleName"] == "M"
        assert name["GenerationCodeOrSuffix"] == "III"

    def test_person_birth_typed_literal(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        birth = doc["hasPersonBirth"]
        assert birth["@type"] == "PersonBirth"
        assert birth["Birthdate"] == {"@type": "xsd:date", "@value": "1965-05-15"}

    def test_person_sex_gender(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        sex = doc["hasPersonSexGender"]
        assert sex["@type"] == "PersonSexGender"
        assert sex["hasSex"] == "Sex_Female"

    def test_identification_typed_literal_token(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        ids = doc["hasPersonIdentification"]
        assert isinstance(ids, list)
        assert len(ids) == 4
        assert ids[0]["PersonIdentifier"] == {"@type": "xsd:token", "@value": "989897099"}

    def test_race_multi_value_array(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        races = doc["hasPersonDemographicRace"]
        assert isinstance(races, list)
        assert len(races) == 2
        # First race group has multiple values
        assert races[0]["hasRaceAndEthnicity"] == [
            "RaceAndEthnicity_White",
            "RaceAndEthnicity_Black",
        ]
        # Second race group has single value — unwrapped from list
        assert races[1]["hasRaceAndEthnicity"] == "RaceAndEthnicity_AmericanIndianOrAlaskaNative"


class TestBuildOneRecordStatus:
    """Test record status and data collection injection."""

    def test_record_status_present(self, person_shape_def, sample_person_row_full, record_status_expected):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        name = doc["hasPersonName"]
        assert name["hasRecordStatus"] == record_status_expected

    def test_data_collection_present(self, person_shape_def, sample_person_row_full, data_collection_expected):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        name = doc["hasPersonName"]
        assert name["hasDataCollection"] == data_collection_expected

    def test_record_status_in_every_sub_shape(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        # Single sub-shapes
        for prop in ("hasPersonBirth", "hasPersonName", "hasPersonSexGender"):
            assert "hasRecordStatus" in doc[prop], f"Missing hasRecordStatus in {prop}"
            assert "hasDataCollection" in doc[prop], f"Missing hasDataCollection in {prop}"
        # Multi sub-shapes (check first instance)
        for prop in ("hasPersonDemographicRace", "hasPersonIdentification"):
            nodes = doc[prop]
            if isinstance(nodes, list):
                for node in nodes:
                    assert "hasRecordStatus" in node, f"Missing hasRecordStatus in {prop}"
                    assert "hasDataCollection" in node, f"Missing hasDataCollection in {prop}"

    def test_record_status_instances_are_independent(self, person_shape_def, sample_person_row_full):
        """Verify each sub-shape gets its own copy — not shared references."""
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        rs1 = doc["hasPersonName"]["hasRecordStatus"]
        rs2 = doc["hasPersonBirth"]["hasRecordStatus"]
        assert rs1 == rs2
        assert rs1 is not rs2  # must be separate dict instances


class TestBuildOneSingleVsArray:
    """Test single instance unwrapping."""

    def test_single_cardinality_is_object(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        assert isinstance(doc["hasPersonName"], dict)
        assert isinstance(doc["hasPersonBirth"], dict)
        assert isinstance(doc["hasPersonSexGender"], dict)

    def test_multiple_cardinality_is_list(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_full))
        assert isinstance(doc["hasPersonDemographicRace"], list)
        assert isinstance(doc["hasPersonIdentification"], list)

    def test_single_instance_multi_cardinality_is_object(self, person_shape_def, sample_person_row_minimal):
        """When multi-cardinality has only 1 instance, unwrap to object."""
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        doc = builder.build_one(mapper.map(sample_person_row_minimal))
        # Minimal row has single race and single ID → unwrapped
        assert isinstance(doc["hasPersonDemographicRace"], dict)
        assert isinstance(doc["hasPersonIdentification"], dict)


class TestBuildMany:
    """Test batch building."""

    def test_build_many_returns_list(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)
        mapped = mapper.map(sample_person_row_full)
        docs = builder.build_many([mapped, mapped, mapped])
        assert len(docs) == 3
        assert all(d["@type"] == "Person" for d in docs)

    def test_build_many_empty(self, person_shape_def):
        builder = JSONLDBuilder(person_shape_def)
        assert builder.build_many([]) == []


class TestBuildOneErrors:
    """Test error handling."""

    def test_missing_id_raises_build_error(self, person_shape_def):
        builder = JSONLDBuilder(person_shape_def)
        with pytest.raises(BuildError, match="__id__"):
            builder.build_one({"hasPersonName": [{"FirstName": "X"}]})

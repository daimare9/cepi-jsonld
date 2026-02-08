"""Tests for FieldMapper."""

from __future__ import annotations

import pytest

from ceds_jsonld.exceptions import MappingError
from ceds_jsonld.mapping import FieldMapper


class TestFieldMapperID:
    """Test document ID extraction."""

    def test_extracts_id_with_transform(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        result = mapper.map(sample_person_row_full)
        assert result["__id__"] == "989897099"

    def test_single_id_no_pipe(self, person_shape_def, sample_person_row_minimal):
        mapper = FieldMapper(person_shape_def.mapping_config)
        result = mapper.map(sample_person_row_minimal)
        assert result["__id__"] == "123456789"

    def test_missing_id_source_raises(self, person_shape_def):
        mapper = FieldMapper(person_shape_def.mapping_config)
        with pytest.raises(MappingError, match="ID source"):
            mapper.map({"FirstName": "Jane"})


class TestFieldMapperSingle:
    """Test single-cardinality property mapping."""

    def test_person_name_all_fields(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        result = mapper.map(sample_person_row_full)
        names = result["hasPersonName"]
        assert len(names) == 1
        name = names[0]
        assert name["FirstName"] == "EDITH"
        assert name["LastOrSurname"] == "ADAMS"
        assert name["MiddleName"] == "M"
        assert name["GenerationCodeOrSuffix"] == "III"

    def test_person_name_optional_fields_absent(self, person_shape_def, sample_person_row_minimal):
        mapper = FieldMapper(person_shape_def.mapping_config)
        result = mapper.map(sample_person_row_minimal)
        name = result["hasPersonName"][0]
        assert name["FirstName"] == "Jane"
        assert name["LastOrSurname"] == "Doe"
        assert "MiddleName" not in name
        assert "GenerationCodeOrSuffix" not in name

    def test_person_birth(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        result = mapper.map(sample_person_row_full)
        birth = result["hasPersonBirth"]
        assert len(birth) == 1
        assert birth[0]["Birthdate"] == "1965-05-15"

    def test_person_sex_gender_transform(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        result = mapper.map(sample_person_row_full)
        sex = result["hasPersonSexGender"]
        assert len(sex) == 1
        assert sex[0]["hasSex"] == "Sex_Female"


class TestFieldMapperMultiple:
    """Test multiple-cardinality property mapping."""

    def test_race_multi_instance(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        result = mapper.map(sample_person_row_full)
        races = result["hasPersonDemographicRace"]
        assert len(races) == 2
        # First instance: White and Black (multi_value_split)
        assert races[0]["hasRaceAndEthnicity"] == [
            "RaceAndEthnicity_White",
            "RaceAndEthnicity_Black",
        ]
        # Second instance: single race
        assert races[1]["hasRaceAndEthnicity"] == [
            "RaceAndEthnicity_AmericanIndianOrAlaskaNative",
        ]

    def test_identification_multi_instance(self, person_shape_def, sample_person_row_full):
        mapper = FieldMapper(person_shape_def.mapping_config)
        result = mapper.map(sample_person_row_full)
        ids = result["hasPersonIdentification"]
        assert len(ids) == 4
        # First identifier
        assert ids[0]["PersonIdentifier"] == "989897099"
        assert ids[0]["hasPersonIdentificationSystem"] == "PersonIdentificationSystem_SSN"
        assert ids[0]["hasPersonIdentifierType"] == "PersonIdentifierType_PersonIdentifier"
        # Third identifier
        assert ids[2]["PersonIdentifier"] == "6202378625"
        assert ids[2]["hasPersonIdentificationSystem"] == "PersonIdentificationSystem_State"

    def test_single_race_value(self, person_shape_def, sample_person_row_minimal):
        mapper = FieldMapper(person_shape_def.mapping_config)
        result = mapper.map(sample_person_row_minimal)
        races = result["hasPersonDemographicRace"]
        assert len(races) == 1
        assert races[0]["hasRaceAndEthnicity"] == ["RaceAndEthnicity_White"]


class TestFieldMapperEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_string_optional_field_skipped(self, person_shape_def):
        mapper = FieldMapper(person_shape_def.mapping_config)
        row = {
            "FirstName": "Jane",
            "MiddleName": "",
            "LastName": "Doe",
            "GenerationCodeOrSuffix": "",
            "Birthdate": "1990-01-01",
            "Sex": "Female",
            "RaceEthnicity": "White",
            "PersonIdentifiers": "123456789",
            "IdentificationSystems": "PersonIdentificationSystem_SSN",
            "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
        }
        result = mapper.map(row)
        name = result["hasPersonName"][0]
        assert "MiddleName" not in name
        assert "GenerationCodeOrSuffix" not in name

    def test_custom_transform(self, person_shape_def):
        custom = {"sex_prefix": lambda v: f"CUSTOM_{v}"}
        mapper = FieldMapper(person_shape_def.mapping_config, custom_transforms=custom)
        row = {
            "FirstName": "Jane",
            "LastName": "Doe",
            "Birthdate": "1990-01-01",
            "Sex": "Female",
            "RaceEthnicity": "White",
            "PersonIdentifiers": "123456789",
            "IdentificationSystems": "PersonIdentificationSystem_SSN",
            "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
        }
        result = mapper.map(row)
        assert result["hasPersonSexGender"][0]["hasSex"] == "CUSTOM_Female"

    def test_pandas_float_in_id(self, person_shape_def):
        """Simulate pandas reading numeric columns as float."""
        mapper = FieldMapper(person_shape_def.mapping_config)
        row = {
            "FirstName": "Jane",
            "LastName": "Doe",
            "Birthdate": "1990-01-01",
            "Sex": "Female",
            "RaceEthnicity": "White",
            "PersonIdentifiers": "123456789.0",
            "IdentificationSystems": "PersonIdentificationSystem_SSN",
            "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
        }
        result = mapper.map(row)
        assert result["__id__"] == "123456789"


# ===================================================================
# Override tests
# ===================================================================


class TestFieldMapperOverrides:
    """Test with_overrides() for source and transform overrides."""

    def test_source_override_renames_column(self, person_shape_def, sample_person_row_minimal):
        mapper = FieldMapper(person_shape_def.mapping_config)
        # Override: PersonName.FirstName reads from "FIRST_NM" instead of "FirstName"
        overridden = mapper.with_overrides(source_overrides={"hasPersonName": {"FirstName": "FIRST_NM"}})

        # Build a row with the new column name
        row = dict(sample_person_row_minimal)
        row["FIRST_NM"] = "Janet"
        del row["FirstName"]

        result = overridden.map(row)
        assert result["hasPersonName"][0]["FirstName"] == "Janet"

    def test_original_mapper_unchanged(self, person_shape_def, sample_person_row_minimal):
        mapper = FieldMapper(person_shape_def.mapping_config)
        _overridden = mapper.with_overrides(source_overrides={"hasPersonName": {"FirstName": "FIRST_NM"}})
        # Original should still use "FirstName"
        result = mapper.map(sample_person_row_minimal)
        assert result["hasPersonName"][0]["FirstName"] == "Jane"

    def test_transform_override(self, person_shape_def, sample_person_row_minimal):
        mapper = FieldMapper(person_shape_def.mapping_config)
        overridden = mapper.with_overrides(transform_overrides={"hasPersonSexGender": {"hasSex": None}})
        result = overridden.map(sample_person_row_minimal)
        # Without the sex_prefix transform, raw value is passed through
        assert result["hasPersonSexGender"][0]["hasSex"] == "Female"

    def test_id_source_override(self, person_shape_def):
        mapper = FieldMapper(person_shape_def.mapping_config)
        overridden = mapper.with_overrides(id_source="CustomID", id_transform=None)
        row = {
            "CustomID": "MY-CUSTOM-001",
            "FirstName": "Jane",
            "LastName": "Doe",
            "Birthdate": "1990-01-01",
            "Sex": "Female",
            "RaceEthnicity": "White",
            "PersonIdentifiers": "123456789",
            "IdentificationSystems": "PersonIdentificationSystem_SSN",
            "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
        }
        result = overridden.map(row)
        assert result["__id__"] == "MY-CUSTOM-001"

    def test_override_nonexistent_property_ignored(self, person_shape_def, sample_person_row_minimal):
        mapper = FieldMapper(person_shape_def.mapping_config)
        # Override a property that doesn't exist — should not raise
        overridden = mapper.with_overrides(source_overrides={"fakeProperty": {"fakeField": "fakeColumn"}})
        result = overridden.map(sample_person_row_minimal)
        assert result["__id__"] == "123456789"

    def test_config_property_returns_copy(self, person_shape_def):
        mapper = FieldMapper(person_shape_def.mapping_config)
        cfg1 = mapper.config
        cfg2 = mapper.config
        assert cfg1 == cfg2
        assert cfg1 is not cfg2  # Must be a copy, not the same object


# ===================================================================
# Composition tests
# ===================================================================


class TestFieldMapperCompose:
    """Test compose() for merging base + overlay configs."""

    def test_compose_overwrites_scalar(self, person_shape_def):
        base = person_shape_def.mapping_config
        overlay = {"id_source": "NewIDColumn", "type": "CustomPerson"}
        mapper = FieldMapper.compose(base, overlay)
        cfg = mapper.config
        assert cfg["id_source"] == "NewIDColumn"
        assert cfg["type"] == "CustomPerson"
        # Inherited from base
        assert "properties" in cfg
        assert len(cfg["properties"]) == 5

    def test_compose_merges_fields(self, person_shape_def):
        base = person_shape_def.mapping_config
        overlay = {
            "properties": {
                "hasPersonName": {
                    "fields": {
                        "Nickname": {
                            "source": "NickName",
                            "target": "Nickname",
                            "optional": True,
                        }
                    }
                }
            }
        }
        mapper = FieldMapper.compose(base, overlay)
        name_fields = mapper.config["properties"]["hasPersonName"]["fields"]
        # Original fields still present
        assert "FirstName" in name_fields
        assert "LastOrSurname" in name_fields
        # New field added
        assert "Nickname" in name_fields

    def test_compose_adds_new_property(self, person_shape_def):
        base = person_shape_def.mapping_config
        overlay = {
            "properties": {
                "hasCustomProperty": {
                    "type": "CustomType",
                    "cardinality": "single",
                    "fields": {"customField": {"source": "CUSTOM_COL", "target": "customField"}},
                }
            }
        }
        mapper = FieldMapper.compose(base, overlay)
        assert "hasCustomProperty" in mapper.config["properties"]
        assert len(mapper.config["properties"]) == 6  # 5 original + 1 new

    def test_compose_merges_record_status_defaults(self, person_shape_def):
        base = person_shape_def.mapping_config
        overlay = {
            "record_status_defaults": {
                "CommittedByOrganization": {"value_id": "cepi:organization/NEWORG"},
            }
        }
        mapper = FieldMapper.compose(base, overlay)
        rs = mapper.config["record_status_defaults"]
        assert rs["CommittedByOrganization"]["value_id"] == "cepi:organization/NEWORG"
        # type should still be there from base
        assert rs["type"] == "RecordStatus"

    def test_compose_does_not_mutate_base(self, person_shape_def):
        import copy

        base = person_shape_def.mapping_config
        original_base = copy.deepcopy(base)
        overlay = {"type": "Modified"}
        _mapper = FieldMapper.compose(base, overlay)
        assert base == original_base

    def test_compose_end_to_end(self, person_shape_def):
        """Compose a mapper and actually map a row to verify it works."""
        base = person_shape_def.mapping_config
        overlay = {
            "properties": {"hasPersonName": {"fields": {"FirstName": {"source": "FNAME", "target": "FirstName"}}}}
        }
        mapper = FieldMapper.compose(base, overlay)
        row = {
            "FNAME": "Composed",
            "LastName": "User",
            "Birthdate": "2000-01-01",
            "Sex": "Male",
            "RaceEthnicity": "White",
            "PersonIdentifiers": "111|222",
            "IdentificationSystems": "PersonIdentificationSystem_SSN|PersonIdentificationSystem_State",
            "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier|PersonIdentifierType_StudentIdentifier",
        }
        result = mapper.map(row)
        assert result["hasPersonName"][0]["FirstName"] == "Composed"
        assert result["__id__"] == "111"

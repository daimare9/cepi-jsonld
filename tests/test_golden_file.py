"""Golden file test — verify full Person output matches reference output.

This compares our generic YAML-driven pipeline against the hand-verified
output produced by the reference ``build_person_direct()`` function from
``ResearchFiles/benchmark_direct_scale.py``.
"""

from __future__ import annotations

from ceds_jsonld.builder import JSONLDBuilder
from ceds_jsonld.mapping import FieldMapper


def _build_expected_record_status() -> dict:
    """Construct the expected record status sub-shape."""
    return {
        "@type": "RecordStatus",
        "RecordStartDateTime": {"@type": "xsd:dateTime", "@value": "1900-01-01T00:00:00"},
        "RecordEndDateTime": {"@type": "xsd:dateTime", "@value": "9999-12-31T00:00:00"},
        "CommittedByOrganization": {"@id": "cepi:organization/3000000789"},
    }


def _build_expected_data_collection() -> dict:
    return {"@id": "http://example.org/dataCollection/45678", "@type": "DataCollection"}


def _build_expected_person_row1() -> dict:
    """Hand-verified expected output for CSV row 1 (EDITH ADAMS)."""
    rs = _build_expected_record_status
    dc = _build_expected_data_collection
    return {
        "@context": "https://cepi-dev.state.mi.us/ontology/context-person.json",
        "@id": "cepi:person/989897099",
        "@type": "Person",
        "hasPersonDemographicRace": [
            {
                "@type": "PersonDemographicRace",
                "hasRaceAndEthnicity": ["RaceAndEthnicity_White", "RaceAndEthnicity_Black"],
                "hasRecordStatus": rs(),
                "hasDataCollection": dc(),
            },
            {
                "@type": "PersonDemographicRace",
                "hasRaceAndEthnicity": "RaceAndEthnicity_AmericanIndianOrAlaskaNative",
                "hasRecordStatus": rs(),
                "hasDataCollection": dc(),
            },
        ],
        "hasPersonIdentification": [
            {
                "@type": "PersonIdentification",
                "PersonIdentifier": {"@type": "xsd:token", "@value": "989897099"},
                "hasPersonIdentificationSystem": "PersonIdentificationSystem_SSN",
                "hasPersonIdentifierType": "PersonIdentifierType_PersonIdentifier",
                "hasRecordStatus": rs(),
                "hasDataCollection": dc(),
            },
            {
                "@type": "PersonIdentification",
                "PersonIdentifier": {"@type": "xsd:token", "@value": "40420"},
                "hasPersonIdentificationSystem": "PersonIdentificationSystem_EducatorID",
                "hasPersonIdentifierType": "PersonIdentifierType_StaffMemberIdentifier",
                "hasRecordStatus": rs(),
                "hasDataCollection": dc(),
            },
            {
                "@type": "PersonIdentification",
                "PersonIdentifier": {"@type": "xsd:token", "@value": "6202378625"},
                "hasPersonIdentificationSystem": "PersonIdentificationSystem_State",
                "hasPersonIdentifierType": "PersonIdentifierType_StudentIdentifier",
                "hasRecordStatus": rs(),
                "hasDataCollection": dc(),
            },
            {
                "@type": "PersonIdentification",
                "PersonIdentifier": {"@type": "xsd:token", "@value": "124031"},
                "hasPersonIdentificationSystem": "PersonIdentificationSystem_SSN",
                "hasPersonIdentifierType": "PersonIdentifierType_StaffMemberIdentifier",
                "hasRecordStatus": rs(),
                "hasDataCollection": dc(),
            },
        ],
        "hasPersonBirth": {
            "@type": "PersonBirth",
            "Birthdate": {"@type": "xsd:date", "@value": "1965-05-15"},
            "hasRecordStatus": rs(),
            "hasDataCollection": dc(),
        },
        "hasPersonName": {
            "@type": "PersonName",
            "FirstName": "EDITH",
            "MiddleName": "M",
            "LastOrSurname": "ADAMS",
            "GenerationCodeOrSuffix": "III",
            "hasRecordStatus": rs(),
            "hasDataCollection": dc(),
        },
        "hasPersonSexGender": {
            "@type": "PersonSexGender",
            "hasSex": "Sex_Female",
            "hasRecordStatus": rs(),
            "hasDataCollection": dc(),
        },
    }


class TestPersonGoldenFile:
    """Verify full Person JSON-LD exactly matches reference output."""

    def test_full_person_row1_matches_expected(self, person_shape_def, sample_person_row_full):
        """Our generic pipeline must produce identical output to build_person_direct."""
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)

        actual = builder.build_one(mapper.map(sample_person_row_full))
        expected = _build_expected_person_row1()

        # Compare each section for better error messages
        assert actual["@context"] == expected["@context"]
        assert actual["@id"] == expected["@id"]
        assert actual["@type"] == expected["@type"]
        assert actual["hasPersonDemographicRace"] == expected["hasPersonDemographicRace"]
        assert actual["hasPersonIdentification"] == expected["hasPersonIdentification"]
        assert actual["hasPersonBirth"] == expected["hasPersonBirth"]
        assert actual["hasPersonName"] == expected["hasPersonName"]
        assert actual["hasPersonSexGender"] == expected["hasPersonSexGender"]

        # Full document equality
        assert actual == expected

    def test_minimal_person_row(self, person_shape_def, sample_person_row_minimal):
        """Minimal row produces valid JSON-LD without optional fields."""
        mapper = FieldMapper(person_shape_def.mapping_config)
        builder = JSONLDBuilder(person_shape_def)

        doc = builder.build_one(mapper.map(sample_person_row_minimal))

        assert doc["@id"] == "cepi:person/123456789"
        assert doc["@type"] == "Person"
        name = doc["hasPersonName"]
        assert name["FirstName"] == "Jane"
        assert name["LastOrSurname"] == "Doe"
        assert "MiddleName" not in name
        assert "GenerationCodeOrSuffix" not in name

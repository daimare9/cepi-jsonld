"""Shared test fixtures for ceds-jsonld."""

from __future__ import annotations

import pytest

from ceds_jsonld.registry import ShapeRegistry


@pytest.fixture()
def person_shape_def():
    """Load the Person shape definition from shipped ontologies."""
    registry = ShapeRegistry()
    return registry.load_shape("person")


@pytest.fixture()
def sample_person_row_full() -> dict:
    """First row of person_sample.csv — full multi-value data."""
    return {
        "FirstName": "EDITH",
        "MiddleName": "M",
        "LastName": "ADAMS",
        "GenerationCodeOrSuffix": "III",
        "Birthdate": "1965-05-15",
        "Sex": "Female",
        "RaceEthnicity": "White,Black|AmericanIndianOrAlaskaNative",
        "PersonIdentifiers": "989897099|40420|6202378625|124031",
        "IdentificationSystems": (
            "PersonIdentificationSystem_SSN|PersonIdentificationSystem_EducatorID"
            "|PersonIdentificationSystem_State|PersonIdentificationSystem_SSN"
        ),
        "PersonIdentifierTypes": (
            "PersonIdentifierType_PersonIdentifier|PersonIdentifierType_StaffMemberIdentifier"
            "|PersonIdentifierType_StudentIdentifier|PersonIdentifierType_StaffMemberIdentifier"
        ),
    }


@pytest.fixture()
def sample_person_row_minimal() -> dict:
    """Minimal valid Person row — single values, no optional fields."""
    return {
        "FirstName": "Jane",
        "LastName": "Doe",
        "Birthdate": "1990-01-15",
        "Sex": "Female",
        "RaceEthnicity": "White",
        "PersonIdentifiers": "123456789",
        "IdentificationSystems": "PersonIdentificationSystem_SSN",
        "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
    }


@pytest.fixture()
def record_status_expected() -> dict:
    """Expected record status sub-shape."""
    return {
        "@type": "RecordStatus",
        "RecordStartDateTime": {"@type": "xsd:dateTime", "@value": "1900-01-01T00:00:00"},
        "RecordEndDateTime": {"@type": "xsd:dateTime", "@value": "9999-12-31T00:00:00"},
        "CommittedByOrganization": {"@id": "cepi:organization/3000000789"},
    }


@pytest.fixture()
def data_collection_expected() -> dict:
    """Expected data collection sub-shape."""
    return {
        "@id": "http://example.org/dataCollection/45678",
        "@type": "DataCollection",
    }

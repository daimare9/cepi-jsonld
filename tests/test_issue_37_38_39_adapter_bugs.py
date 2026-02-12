"""Tests for issues #37, #38, and #39.

#37 — OneRosterAdapter._flatten_record silently drops all list elements
      beyond the first, causing data loss. Fixed to use indexed keys
      (e.g. ``org_0_sourcedId``, ``org_1_sourcedId``) and raise on
      key collisions.

#38 — OneRosterAdapter rejects standard 'students' and 'teachers'
      endpoints.  Fixed by adding them (plus 'terms', 'categories')
      to ``_ONEROSTER_RESOURCES``.

#39 — powerschool_adapter() factory sets dot-notation ``results_key``
      values (e.g. ``"students.student"``), but APIAdapter._extract_records
      does a flat dict lookup instead of nested path traversal.  Fixed by
      splitting on ``"."`` and traversing.
"""

from __future__ import annotations

from typing import Any

import pytest

from ceds_jsonld.adapters.api_adapter import APIAdapter
from ceds_jsonld.exceptions import AdapterError


# ======================================================================
# Issue #38 — OneRoster must accept 'students', 'teachers', etc.
# ======================================================================


class TestOneRosterResourceValidation:
    """_ONEROSTER_RESOURCES must include all standard OneRoster 1.1 endpoints."""

    @pytest.mark.parametrize(
        "resource",
        ["students", "teachers", "terms", "categories"],
    )
    def test_new_resources_accepted(self, resource: str) -> None:
        """Standard OneRoster endpoints must not raise AdapterError."""
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        adapter = OneRosterAdapter(
            "https://sis.example.com/ims/oneroster/v1p1",
            resource,
            bearer_token="tok",
        )
        assert adapter._resource == resource

    @pytest.mark.parametrize(
        "resource",
        [
            "users",
            "orgs",
            "enrollments",
            "courses",
            "classes",
            "academicSessions",
            "demographics",
            "lineItems",
            "results",
            "gradingPeriods",
        ],
    )
    def test_existing_resources_still_accepted(self, resource: str) -> None:
        """Original resources must remain valid after the addition."""
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        adapter = OneRosterAdapter(
            "https://sis.example.com",
            resource,
            bearer_token="tok",
        )
        assert adapter._resource == resource

    def test_invalid_resource_still_rejected(self) -> None:
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        with pytest.raises(AdapterError, match="Unknown OneRoster resource"):
            OneRosterAdapter("https://sis.example.com", "unicorns", bearer_token="tok")


# ======================================================================
# Issue #37 — _flatten_record must preserve all list elements
# ======================================================================


class TestFlattenRecordIndexed:
    """_flatten_record must use indexed keys and detect collisions."""

    def test_single_element_list(self) -> None:
        """A list with one dict should produce index-0 keys."""
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        record = {
            "sourcedId": "stu-001",
            "orgs": [{"sourcedId": "org-A", "type": "school"}],
        }
        flat = OneRosterAdapter._flatten_record(record)

        assert flat["sourcedId"] == "stu-001"
        assert flat["org_0_sourcedId"] == "org-A"
        assert flat["org_0_type"] == "school"
        assert flat["orgs_count"] == 1

    def test_multiple_element_list_all_preserved(self) -> None:
        """All list elements must be preserved with indexed keys."""
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        record = {
            "sourcedId": "stu-001",
            "givenName": "Jane",
            "orgs": [
                {"sourcedId": "org-A", "type": "school", "name": "Lincoln Elementary"},
                {"sourcedId": "org-B", "type": "district", "name": "District 47"},
                {"sourcedId": "org-C", "type": "state", "name": "State DOE"},
            ],
        }
        flat = OneRosterAdapter._flatten_record(record)

        # All three orgs preserved
        assert flat["org_0_sourcedId"] == "org-A"
        assert flat["org_0_name"] == "Lincoln Elementary"
        assert flat["org_1_sourcedId"] == "org-B"
        assert flat["org_1_name"] == "District 47"
        assert flat["org_2_sourcedId"] == "org-C"
        assert flat["org_2_name"] == "State DOE"
        assert flat["orgs_count"] == 3
        # Scalar fields preserved
        assert flat["sourcedId"] == "stu-001"
        assert flat["givenName"] == "Jane"

    def test_nested_dict_flattened(self) -> None:
        """Plain nested dicts (not in a list) still flatten correctly."""
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        record = {
            "sourcedId": "e1",
            "user": {"sourcedId": "u1", "givenName": "Alice"},
        }
        flat = OneRosterAdapter._flatten_record(record)

        assert flat["user_sourcedId"] == "u1"
        assert flat["user_givenName"] == "Alice"
        assert flat["sourcedId"] == "e1"

    def test_key_collision_raises(self) -> None:
        """Key collision between a nested dict and an existing flat key must raise."""
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        record = {
            "org_type": "existing_value",
            "org": {"type": "school"},
        }
        with pytest.raises(AdapterError, match="Key collision"):
            OneRosterAdapter._flatten_record(record)

    def test_empty_list_preserved_as_scalar(self) -> None:
        """An empty list is not a list-of-dicts — it stays as a scalar."""
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        record = {"sourcedId": "x", "tags": []}
        flat = OneRosterAdapter._flatten_record(record)
        assert flat["tags"] == []

    def test_list_of_scalars_preserved(self) -> None:
        """A list of plain scalars (not dicts) stays intact."""
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        record = {"sourcedId": "x", "grades": ["A", "B", "C"]}
        flat = OneRosterAdapter._flatten_record(record)
        assert flat["grades"] == ["A", "B", "C"]

    def test_mixed_record_complex(self) -> None:
        """Real-world-like record with dict, list-of-dicts, and scalars."""
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        record = {
            "sourcedId": "e1",
            "role": "student",
            "user": {"sourcedId": "u1", "givenName": "Alice"},
            "orgs": [
                {"sourcedId": "org1", "type": "school"},
                {"sourcedId": "org2", "type": "district"},
            ],
        }
        flat = OneRosterAdapter._flatten_record(record)

        assert flat["sourcedId"] == "e1"
        assert flat["role"] == "student"
        assert flat["user_sourcedId"] == "u1"
        assert flat["org_0_sourcedId"] == "org1"
        assert flat["org_1_sourcedId"] == "org2"
        assert flat["orgs_count"] == 2


# ======================================================================
# Issue #39 — APIAdapter._extract_records must support dot-notation
# ======================================================================


class TestExtractRecordsDotPath:
    """_extract_records must traverse nested paths when results_key has dots."""

    def test_flat_key_still_works(self) -> None:
        """Single-segment results_key should work as before."""
        adapter = APIAdapter("http://example.com", results_key="data")
        records = adapter._extract_records({"data": [{"id": 1}]})
        assert records == [{"id": 1}]

    def test_dot_path_traversal(self) -> None:
        """Dot-notation key like 'students.student' must traverse nested dicts."""
        adapter = APIAdapter("http://example.com", results_key="students.student")
        data = {
            "students": {
                "@expansions": "demographics,addresses",
                "student": [
                    {"id": 1, "name": "Jane"},
                    {"id": 2, "name": "John"},
                ],
            }
        }
        records = adapter._extract_records(data)
        assert len(records) == 2
        assert records[0]["name"] == "Jane"

    def test_three_level_dot_path(self) -> None:
        """Three-segment path must also work."""
        adapter = APIAdapter("http://example.com", results_key="a.b.c")
        data = {"a": {"b": {"c": [{"x": 1}]}}}
        records = adapter._extract_records(data)
        assert records == [{"x": 1}]

    def test_missing_intermediate_key_raises(self) -> None:
        """Missing intermediate key must raise AdapterError."""
        adapter = APIAdapter("http://example.com", results_key="students.student")
        with pytest.raises(AdapterError, match="missing expected key 'students.student'"):
            adapter._extract_records({"other": {}})

    def test_missing_leaf_key_raises(self) -> None:
        """Missing leaf key must raise AdapterError."""
        adapter = APIAdapter("http://example.com", results_key="students.student")
        with pytest.raises(AdapterError, match="missing expected key"):
            adapter._extract_records({"students": {"other": []}})

    def test_no_results_key_returns_list_directly(self) -> None:
        """When results_key is None, the response itself must be a list."""
        adapter = APIAdapter("http://example.com")
        records = adapter._extract_records([{"id": 1}])
        assert records == [{"id": 1}]

    def test_powerschool_all_resources(self) -> None:
        """Every PowerSchool resource must extract correctly with dot-path."""
        from ceds_jsonld.adapters.sis_factories import powerschool_adapter

        test_cases: list[tuple[str, str, dict[str, Any]]] = [
            ("students", "students.student", {"students": {"student": [{"id": 1}]}}),
            ("staff", "staff.staff", {"staff": {"staff": [{"id": 2}]}}),
            ("schools", "schools.school", {"schools": {"school": [{"id": 3}]}}),
            ("sections", "sections.section", {"sections": {"section": [{"id": 4}]}}),
            ("enrollments", "enrollments.enrollment", {"enrollments": {"enrollment": [{"id": 5}]}}),
        ]
        for resource, expected_key, response_data in test_cases:
            adapter = powerschool_adapter("https://ps.example.com", "tok", resource)
            assert adapter._results_key == expected_key
            records = adapter._extract_records(response_data)
            assert len(records) == 1, f"Failed for resource={resource}"

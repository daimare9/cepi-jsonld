"""Tests for issue #21 — Pipeline.validate() double-counts errors/warnings.

The root cause: Pipeline.validate() manually incremented error_count /
warning_count AND called result.add_issue() which also increments them.
"""

from __future__ import annotations

from ceds_jsonld import DictAdapter, Pipeline, ShapeRegistry
from ceds_jsonld.validator import ValidationMode


def _make_pipeline(rows: list[dict]) -> Pipeline:
    registry = ShapeRegistry()
    registry.load_shape("person")
    return Pipeline(DictAdapter(rows), "person", registry)


class TestValidateCountAccuracy:
    """Verify error_count / warning_count match actual FieldIssue objects."""

    def test_error_count_matches_issue_count(self) -> None:
        """error_count must equal the number of error FieldIssue objects."""
        row = {
            "FirstName": "",
            "LastName": "",
            "Birthdate": "",
            "Sex": "",
            "PersonIdentifiers": "12345",
            "IdentificationSystems": "State",
        }
        pipeline = _make_pipeline([row])
        result = pipeline.validate(mode=ValidationMode.REPORT)

        actual_errors = sum(
            1
            for issues in result.issues.values()
            for i in issues
            if i.severity == "error"
        )
        assert actual_errors > 0, "Test expects at least one error"
        assert result.error_count == actual_errors, (
            f"error_count ({result.error_count}) != actual error issues ({actual_errors})"
        )

    def test_warning_count_matches_issue_count(self) -> None:
        """warning_count must equal the number of warning FieldIssue objects."""
        row = {
            "FirstName": "Jane",
            "LastName": "Doe",
            "Birthdate": "not-a-date",
            "Sex": "Female",
            "PersonIdentifiers": "12345",
            "IdentificationSystems": "State",
        }
        pipeline = _make_pipeline([row])
        result = pipeline.validate(mode=ValidationMode.REPORT)

        actual_warnings = sum(
            1
            for issues in result.issues.values()
            for i in issues
            if i.severity == "warning"
        )
        assert result.warning_count == actual_warnings, (
            f"warning_count ({result.warning_count}) != actual warning issues ({actual_warnings})"
        )

    def test_no_double_count_multiple_rows(self) -> None:
        """Counts must be accurate across multiple rows."""
        rows = [
            {
                "FirstName": "",
                "LastName": "Doe",
                "Birthdate": "2000-01-01",
                "Sex": "Female",
                "PersonIdentifiers": "1",
                "IdentificationSystems": "State",
            },
            {
                "FirstName": "",
                "LastName": "",
                "Birthdate": "2000-01-01",
                "Sex": "Female",
                "PersonIdentifiers": "2",
                "IdentificationSystems": "State",
            },
        ]
        pipeline = _make_pipeline(rows)
        result = pipeline.validate(mode=ValidationMode.REPORT)

        actual_errors = sum(
            1
            for issues in result.issues.values()
            for i in issues
            if i.severity == "error"
        )
        assert result.error_count == actual_errors

    def test_valid_row_zero_counts(self) -> None:
        """A fully valid row should produce zero errors and zero warnings."""
        row = {
            "FirstName": "Jane",
            "LastName": "Doe",
            "Birthdate": "2000-01-01",
            "Sex": "Female",
            "PersonIdentifiers": "12345",
            "IdentificationSystems": "State",
        }
        pipeline = _make_pipeline([row])
        result = pipeline.validate(mode=ValidationMode.REPORT)

        assert result.error_count == 0
        assert result.warning_count == 0
        assert result.conforms is True

    def test_summary_reflects_accurate_counts(self) -> None:
        """The summary() string must use the corrected (non-inflated) counts."""
        row = {
            "FirstName": "",
            "LastName": "",
            "Birthdate": "",
            "Sex": "",
            "PersonIdentifiers": "12345",
            "IdentificationSystems": "State",
        }
        pipeline = _make_pipeline([row])
        result = pipeline.validate(mode=ValidationMode.REPORT)

        actual_errors = sum(
            1
            for issues in result.issues.values()
            for i in issues
            if i.severity == "error"
        )
        # The summary must contain the accurate count, not 2x
        assert f"{actual_errors} errors" in result.summary()

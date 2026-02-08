"""Tests for issues #19, #20 — Pipeline DLQ metrics and serialization safety.

#19: Pipeline.run()/to_json()/to_ndjson() must track records_failed and dead_letter_path.
#20: DLQ writer must not crash on non-serializable raw_row values.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from ceds_jsonld import DictAdapter, Pipeline, ShapeRegistry


@pytest.fixture()
def _person_registry() -> ShapeRegistry:
    """Pre-loaded person shape registry."""
    reg = ShapeRegistry()
    reg.load_shape("person")
    return reg


def _good_row() -> dict[str, Any]:
    return {
        "FirstName": "Alice",
        "LastName": "Smith",
        "Sex": "Female",
        "Birthdate": "2000-01-01",
        "PersonIdentifiers": "123456789",
        "IdentificationSystems": "PersonIdentificationSystem_State",
    }


def _bad_row() -> dict[str, Any]:
    """Row that will fail mapping/building (empty required fields)."""
    return {
        "FirstName": "Bad",
        "LastName": "Row",
        "Sex": "Female",
        "Birthdate": "2000-02-02",
        "PersonIdentifiers": "",
        "IdentificationSystems": "",
    }


class TestPipelineRecordsFailed:
    """Issue #19 — records_failed and dead_letter_path must reflect DLQ activity."""

    def test_run_tracks_failures(self, _person_registry: ShapeRegistry, tmp_path: Path):
        """Pipeline.run() must set records_failed > 0 when rows fail."""
        rows = [_good_row(), _bad_row()]
        dlq = tmp_path / "dlq.ndjson"
        pipe = Pipeline(DictAdapter(rows), "person", _person_registry, dead_letter_path=dlq)
        result = pipe.run()
        assert result.records_in == 2
        assert result.records_out == 1
        assert result.records_failed == 1
        assert result.dead_letter_path is not None
        assert dlq.exists()

    def test_to_json_tracks_failures(self, _person_registry: ShapeRegistry, tmp_path: Path):
        """Pipeline.to_json() must reflect DLQ failures in result."""
        rows = [_good_row(), _bad_row()]
        dlq = tmp_path / "dlq.ndjson"
        out = tmp_path / "out.json"
        pipe = Pipeline(DictAdapter(rows), "person", _person_registry, dead_letter_path=dlq)
        result = pipe.to_json(out)
        assert result.records_in == 2
        assert result.records_out == 1
        assert result.records_failed == 1
        assert result.dead_letter_path is not None

    def test_to_ndjson_tracks_failures(self, _person_registry: ShapeRegistry, tmp_path: Path):
        """Pipeline.to_ndjson() must reflect DLQ failures in result."""
        rows = [_good_row(), _bad_row()]
        dlq = tmp_path / "dlq.ndjson"
        out = tmp_path / "out.ndjson"
        pipe = Pipeline(DictAdapter(rows), "person", _person_registry, dead_letter_path=dlq)
        result = pipe.to_ndjson(out)
        assert result.records_in == 2
        assert result.records_out == 1
        assert result.records_failed == 1
        assert result.dead_letter_path is not None

    def test_no_failures_no_dlq_path(self, _person_registry: ShapeRegistry, tmp_path: Path):
        """When all rows succeed, dead_letter_path should remain None."""
        rows = [_good_row()]
        dlq = tmp_path / "dlq.ndjson"
        pipe = Pipeline(DictAdapter(rows), "person", _person_registry, dead_letter_path=dlq)
        result = pipe.run()
        assert result.records_failed == 0
        assert result.dead_letter_path is None


class TestDLQNonSerializable:
    """Issue #20 — DLQ writer must gracefully handle non-serializable values."""

    def test_set_value_does_not_crash(self, _person_registry: ShapeRegistry, tmp_path: Path):
        """A row with a set (non-JSON-serializable) should go to DLQ, not crash."""
        rows = [
            {
                "FirstName": {1, 2, 3},  # set — not JSON serializable
                "LastName": "Doe",
                "Sex": "Male",
                "Birthdate": "2000-01-01",
                "PersonIdentifiers": "123",
                "IdentificationSystems": "State",
            },
        ]
        dlq = tmp_path / "dlq.ndjson"
        pipe = Pipeline(DictAdapter(rows), "person", _person_registry, dead_letter_path=dlq)
        result = pipe.run()
        assert result.records_failed == 1
        assert result.records_out == 0
        assert dlq.exists()
        # DLQ content should be parseable JSON
        content = dlq.read_text(encoding="utf-8")
        entry = json.loads(content.strip())
        assert "_error" in entry

    def test_datetime_value_does_not_crash(self, _person_registry: ShapeRegistry, tmp_path: Path):
        """A row with a datetime object should go to DLQ gracefully."""
        rows = [
            {
                "FirstName": datetime(2026, 1, 1),  # not JSON serializable
                "LastName": "Doe",
                "Sex": "Male",
                "Birthdate": "2000-01-01",
                "PersonIdentifiers": "",  # empty required → will fail build
                "IdentificationSystems": "",
            },
        ]
        dlq = tmp_path / "dlq.ndjson"
        pipe = Pipeline(DictAdapter(rows), "person", _person_registry, dead_letter_path=dlq)
        # Should not crash — the DLQ writer must handle the datetime in raw_row
        result = pipe.run()
        assert result.records_failed == 1
        assert dlq.exists()

    def test_normal_row_still_serializes_normally(self, _person_registry: ShapeRegistry, tmp_path: Path):
        """Normal rows should use the fast orjson path, not the fallback."""
        rows = [_good_row(), _bad_row()]
        dlq = tmp_path / "dlq.ndjson"
        pipe = Pipeline(DictAdapter(rows), "person", _person_registry, dead_letter_path=dlq)
        result = pipe.run()
        assert result.records_out == 1
        assert result.records_failed == 1
        # DLQ entry for the normal bad row should NOT have _serialization_fallback
        content = dlq.read_text(encoding="utf-8").strip()
        entry = json.loads(content)
        assert entry.get("_serialization_fallback") is not True

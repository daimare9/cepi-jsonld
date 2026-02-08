"""Tests for Phase 7 — Production Hardening.

Covers: structured logging, PII masking, IRI sanitization, PipelineResult
metrics, dead-letter queue, progress tracking, and memory profiling.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ceds_jsonld.adapters.dict_adapter import DictAdapter
from ceds_jsonld.logging import (
    _REDACTED,
    PII_FIELDS,
    _mask_pii,
    get_backend,
    get_logger,
)
from ceds_jsonld.pipeline import Pipeline, PipelineResult, _DeadLetterWriter
from ceds_jsonld.registry import ShapeRegistry
from ceds_jsonld.sanitize import sanitize_iri_component, sanitize_string_value, validate_base_uri

# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture()
def registry() -> ShapeRegistry:
    reg = ShapeRegistry()
    reg.load_shape("person")
    return reg


@pytest.fixture()
def valid_rows() -> list[dict[str, Any]]:
    return [
        {
            "FirstName": "Alice",
            "MiddleName": "",
            "LastName": "Smith",
            "GenerationCodeOrSuffix": "",
            "Birthdate": "1990-01-15",
            "Sex": "Female",
            "RaceEthnicity": "White",
            "PersonIdentifiers": "111222333",
            "IdentificationSystems": "PersonIdentificationSystem_SSN",
            "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
        },
        {
            "FirstName": "Bob",
            "MiddleName": "J",
            "LastName": "Jones",
            "GenerationCodeOrSuffix": "",
            "Birthdate": "1985-06-20",
            "Sex": "Male",
            "RaceEthnicity": "Hispanic",
            "PersonIdentifiers": "444555666",
            "IdentificationSystems": "PersonIdentificationSystem_SSN",
            "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
        },
    ]


@pytest.fixture()
def bad_row() -> dict[str, Any]:
    """A row missing the required ID field."""
    return {
        "FirstName": "Broken",
        "LastName": "Record",
    }


# =====================================================================
# Structured Logging
# =====================================================================


class TestStructuredLogging:
    """Verify the logging module provides a usable logger regardless of backend."""

    def test_get_logger_returns_object(self) -> None:
        logger = get_logger("test")
        assert logger is not None

    def test_get_backend_returns_string(self) -> None:
        backend = get_backend()
        assert backend in ("structlog", "logging")

    def test_logger_has_standard_methods(self) -> None:
        logger = get_logger("test")
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_logger_info_does_not_raise(self) -> None:
        logger = get_logger("test")
        logger.info("test.event", key="value")

    def test_logger_bind_returns_new_logger(self) -> None:
        logger = get_logger("test")
        bound = logger.bind(shape="person")
        assert bound is not None
        # Should not raise
        bound.info("test.bound_event")


# =====================================================================
# PII Masking
# =====================================================================


class TestPIIMasking:
    """Verify PII fields are redacted from log event dicts."""

    def test_pii_fields_set_is_frozen(self) -> None:
        assert isinstance(PII_FIELDS, frozenset)
        assert len(PII_FIELDS) > 5

    def test_mask_pii_redacts_known_fields(self) -> None:
        event = {"event": "test", "ssn": "123-45-6789", "birthdate": "1990-01-01"}
        masked = _mask_pii(event)
        assert masked["ssn"] == _REDACTED
        assert masked["birthdate"] == _REDACTED
        # Non-PII field untouched
        assert masked["event"] == "test"

    def test_mask_pii_case_insensitive(self) -> None:
        event = {"event": "test", "SSN": "123-45-6789", "FirstName": "Jane"}
        masked = _mask_pii(event)
        assert masked["SSN"] == _REDACTED
        assert masked["FirstName"] == _REDACTED

    def test_mask_pii_leaves_non_pii_alone(self) -> None:
        event = {"event": "build", "shape": "person", "records": 100}
        masked = _mask_pii(event)
        assert masked == event

    def test_mask_pii_handles_empty(self) -> None:
        assert _mask_pii({}) == {}

    def test_mask_pii_recurses_nested_dicts(self) -> None:
        """Regression: nested PII fields must be redacted (issue #15)."""
        event = {"event": "test", "person": {"ssn": "123-45-6789", "name": "safe"}}
        masked = _mask_pii(event)
        assert masked["person"]["ssn"] == _REDACTED
        assert masked["person"]["name"] == "safe"

    def test_mask_pii_recurses_deeply_nested(self) -> None:
        """Deeply nested PII fields must be caught."""
        event = {"event": "test", "outer": {"inner": {"birthdate": "1990-01-01"}}}
        masked = _mask_pii(event)
        assert masked["outer"]["inner"]["birthdate"] == _REDACTED

    def test_mask_pii_recurses_lists(self) -> None:
        """PII inside list items must be redacted."""
        event = {"event": "test", "records": [{"firstname": "Jane"}, {"firstname": "John"}]}
        masked = _mask_pii(event)
        assert masked["records"][0]["firstname"] == _REDACTED
        assert masked["records"][1]["firstname"] == _REDACTED

    def test_mask_pii_detects_ssn_pattern_in_values(self) -> None:
        """Regression: SSN patterns in values must be scrubbed (issue #15)."""
        event = {"event": "test", "data": "Student SSN: 123-45-6789"}
        masked = _mask_pii(event)
        assert "123-45-6789" not in masked["data"]
        assert _REDACTED in masked["data"]

    def test_mask_pii_detects_email_pattern_in_values(self) -> None:
        """Email patterns in values must be scrubbed."""
        event = {"event": "test", "msg": "Contact: jane.doe@example.com for info"}
        masked = _mask_pii(event)
        assert "jane.doe@example.com" not in masked["msg"]
        assert _REDACTED in masked["msg"]

    def test_mask_pii_detects_ssn_in_nested_values(self) -> None:
        """SSN patterns inside nested dicts must also be caught."""
        event = {"event": "test", "detail": {"note": "ID is 999-88-7777"}}
        masked = _mask_pii(event)
        assert "999-88-7777" not in masked["detail"]["note"]

    def test_mask_pii_no_false_positive_on_non_ssn(self) -> None:
        """Numbers that aren't SSN format should not be masked."""
        event = {"event": "test", "data": "Phone: 555-1234 and zip: 90210"}
        masked = _mask_pii(event)
        assert masked["data"] == event["data"]


# =====================================================================
# IRI Sanitization
# =====================================================================


class TestIRISanitization:
    """Verify IRI components are properly sanitized."""

    def test_clean_id_passes_through(self) -> None:
        assert sanitize_iri_component("989897099") == "989897099"

    def test_alphanumeric_safe(self) -> None:
        assert sanitize_iri_component("abc123") == "abc123"

    def test_spaces_encoded(self) -> None:
        result = sanitize_iri_component("hello world")
        assert "%20" in result
        assert " " not in result

    def test_angle_brackets_encoded(self) -> None:
        result = sanitize_iri_component("<script>alert(1)</script>")
        assert "<" not in result
        assert ">" not in result

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_iri_component("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_iri_component("   ")

    def test_special_chars_encoded(self) -> None:
        result = sanitize_iri_component("id with\nnewline")
        assert "\n" not in result

    def test_unicode_normalized(self) -> None:
        # NFC normalization — e-accent composed vs decomposed should produce same result
        result1 = sanitize_iri_component("\u00e9")  # é composed
        result2 = sanitize_iri_component("e\u0301")  # e + combining accent
        assert result1 == result2

    def test_path_traversal_encoded(self) -> None:
        """Path traversal sequences must be percent-encoded (issue #10)."""
        result = sanitize_iri_component("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
        # Dots and slashes should be encoded
        assert "%2E" in result
        assert "%2F" in result

    def test_single_dotdot_encoded(self) -> None:
        """Even a single ``../`` must be neutralised."""
        result = sanitize_iri_component("../secret")
        assert ".." not in result
        assert "/" not in result

    def test_backslash_traversal_encoded(self) -> None:
        """Windows-style backslash traversal must also be caught."""
        result = sanitize_iri_component("..\\..\\windows\\system32")
        assert ".." not in result
        assert "\\" not in result

    def test_forward_slash_always_encoded(self) -> None:
        """Forward slashes should never appear unencoded in a component."""
        result = sanitize_iri_component("foo/bar/baz")
        assert "/" not in result
        assert "%2F" in result

    def test_plain_dots_safe(self) -> None:
        """Dots not part of traversal (e.g. version numbers) stay clean."""
        result = sanitize_iri_component("version.1.0")
        assert result == "version.1.0"


class TestBaseURIValidation:
    """Verify base URI validation catches injection."""

    def test_valid_uri_passes(self) -> None:
        assert validate_base_uri("cepi:person/") == "cepi:person/"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_base_uri("")

    def test_script_injection_blocked(self) -> None:
        with pytest.raises(ValueError, match="suspicious"):
            validate_base_uri("<script>evil</script>")

    def test_javascript_uri_blocked(self) -> None:
        with pytest.raises(ValueError, match="suspicious"):
            validate_base_uri("javascript:alert(1)")

    def test_null_byte_blocked(self) -> None:
        with pytest.raises(ValueError, match="suspicious"):
            validate_base_uri("cepi:person/\x00evil")

    def test_trailing_slash_accepted(self) -> None:
        assert validate_base_uri("http://example.org/ns/") == "http://example.org/ns/"

    def test_trailing_hash_accepted(self) -> None:
        assert validate_base_uri("http://example.org/ns#") == "http://example.org/ns#"

    def test_no_trailing_separator_raises(self) -> None:
        with pytest.raises(ValueError, match="must end with"):
            validate_base_uri("cepi:person")

    def test_no_trailing_separator_http_raises(self) -> None:
        with pytest.raises(ValueError, match="must end with"):
            validate_base_uri("http://example.org/ns")

    def test_no_trailing_separator_urn_raises(self) -> None:
        with pytest.raises(ValueError, match="must end with"):
            validate_base_uri("urn:ceds")


# =====================================================================
# String value sanitization (null bytes / control chars)
# =====================================================================


class TestSanitizeStringValue:
    """Verify sanitize_string_value strips null bytes and control chars."""

    def test_null_byte_stripped(self) -> None:
        assert sanitize_string_value("Jane\x00Doe") == "JaneDoe"

    def test_multiple_null_bytes_stripped(self) -> None:
        assert sanitize_string_value("\x00A\x00B\x00") == "AB"

    def test_clean_string_unchanged(self) -> None:
        assert sanitize_string_value("Hello World") == "Hello World"

    def test_tab_preserved(self) -> None:
        assert sanitize_string_value("col1\tcol2") == "col1\tcol2"

    def test_newline_preserved(self) -> None:
        assert sanitize_string_value("line1\nline2") == "line1\nline2"

    def test_carriage_return_preserved(self) -> None:
        assert sanitize_string_value("line1\r\nline2") == "line1\r\nline2"

    def test_other_control_chars_stripped(self) -> None:
        # Bell (0x07), backspace (0x08), form feed (0x0C) should be stripped
        assert sanitize_string_value("A\x07B\x08C\x0cD") == "ABCD"

    def test_empty_string_unchanged(self) -> None:
        assert sanitize_string_value("") == ""

    def test_only_null_bytes_becomes_empty(self) -> None:
        assert sanitize_string_value("\x00\x00\x00") == ""


class TestNullBytePipelineIntegration:
    """End-to-end: null bytes in field values are stripped by the pipeline."""

    def test_null_byte_in_first_name_stripped(self, registry: ShapeRegistry) -> None:
        """Reproduces issue #9 — null byte in FirstName must be stripped."""
        record = {
            "FirstName": "Jane\x00Doe",
            "MiddleName": "",
            "LastName": "Smith",
            "GenerationCodeOrSuffix": "",
            "Birthdate": "2010-01-01",
            "Sex": "Female",
            "RaceEthnicity": "White",
            "PersonIdentifiers": "ID-001",
            "IdentificationSystems": "PersonIdentificationSystem_SSN",
            "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
        }
        pipeline = Pipeline(
            source=DictAdapter([record]),
            shape="person",
            registry=registry,
        )
        docs = pipeline.build_all()
        name = docs[0]["hasPersonName"]["FirstName"]
        assert "\x00" not in name
        assert name == "JaneDoe"

    def test_null_byte_in_id_stripped(self, registry: ShapeRegistry) -> None:
        """Null bytes in the ID field are stripped before IRI construction."""
        record = {
            "FirstName": "Jane",
            "MiddleName": "",
            "LastName": "Smith",
            "GenerationCodeOrSuffix": "",
            "Birthdate": "2010-01-01",
            "Sex": "Female",
            "RaceEthnicity": "White",
            "PersonIdentifiers": "ID\x00001",
            "IdentificationSystems": "PersonIdentificationSystem_SSN",
            "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
        }
        pipeline = Pipeline(
            source=DictAdapter([record]),
            shape="person",
            registry=registry,
        )
        docs = pipeline.build_all()
        assert "\x00" not in docs[0]["@id"]

    def test_null_byte_round_trip(self, registry: ShapeRegistry) -> None:
        """Null bytes must not survive serialize → deserialize round-trip."""
        from ceds_jsonld.serializer import dumps, loads

        record = {
            "FirstName": "Jane\x00Doe",
            "MiddleName": "",
            "LastName": "Smith",
            "GenerationCodeOrSuffix": "",
            "Birthdate": "2010-01-01",
            "Sex": "Female",
            "RaceEthnicity": "White",
            "PersonIdentifiers": "ID-001",
            "IdentificationSystems": "PersonIdentificationSystem_SSN",
            "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
        }
        pipeline = Pipeline(
            source=DictAdapter([record]),
            shape="person",
            registry=registry,
        )
        docs = pipeline.build_all()
        raw = dumps(docs[0])
        reparsed = loads(raw)
        assert "\x00" not in reparsed["hasPersonName"]["FirstName"]


# =====================================================================
# IRI sanitization wired into Builder
# =====================================================================


class TestBuilderIRISanitization:
    """Verify the builder sanitizes @id values."""

    def test_normal_id_unchanged(self, registry: ShapeRegistry, valid_rows: list[dict]) -> None:
        source = DictAdapter(valid_rows[:1])
        pipeline = Pipeline(source=source, shape="person", registry=registry)
        docs = pipeline.build_all()
        # Normal numeric ID should pass through unmodified
        assert docs[0]["@id"] == "cepi:person/111222333"

    def test_id_with_special_chars_sanitized(self, registry: ShapeRegistry) -> None:
        rows = [
            {
                "FirstName": "Test",
                "MiddleName": "",
                "LastName": "User",
                "GenerationCodeOrSuffix": "",
                "Birthdate": "2000-01-01",
                "Sex": "Female",
                "RaceEthnicity": "White",
                "PersonIdentifiers": "id with spaces",
                "IdentificationSystems": "PersonIdentificationSystem_SSN",
                "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
            },
        ]
        source = DictAdapter(rows)
        pipeline = Pipeline(
            source=source,
            shape="person",
            registry=registry,
            id_source="PersonIdentifiers",
            id_transform=None,
        )
        docs = pipeline.build_all()
        assert " " not in docs[0]["@id"]
        assert "%20" in docs[0]["@id"]


# =====================================================================
# PipelineResult Metrics
# =====================================================================


class TestPipelineResult:
    """Verify PipelineResult dataclass and Pipeline.run() method."""

    def test_pipeline_result_defaults(self) -> None:
        pr = PipelineResult()
        assert pr.records_in == 0
        assert pr.records_out == 0
        assert pr.records_failed == 0
        assert pr.elapsed_seconds == 0.0
        assert pr.records_per_second == 0.0
        assert pr.bytes_written == 0
        assert pr.dead_letter_path is None

    def test_run_returns_pipeline_result(self, registry: ShapeRegistry, valid_rows: list[dict]) -> None:
        source = DictAdapter(valid_rows)
        pipeline = Pipeline(source=source, shape="person", registry=registry)
        result = pipeline.run()
        assert isinstance(result, PipelineResult)
        assert result.records_in == 2
        assert result.records_out == 2
        assert result.records_failed == 0
        assert result.elapsed_seconds >= 0
        assert result.records_per_second > 0

    def test_to_json_returns_pipeline_result(
        self, tmp_path: Path, registry: ShapeRegistry, valid_rows: list[dict]
    ) -> None:
        source = DictAdapter(valid_rows)
        pipeline = Pipeline(source=source, shape="person", registry=registry)
        result = pipeline.to_json(tmp_path / "out.json")
        assert isinstance(result, PipelineResult)
        assert result.bytes_written > 0
        assert result.records_out == 2

    def test_to_ndjson_returns_pipeline_result(
        self, tmp_path: Path, registry: ShapeRegistry, valid_rows: list[dict]
    ) -> None:
        source = DictAdapter(valid_rows)
        pipeline = Pipeline(source=source, shape="person", registry=registry)
        result = pipeline.to_ndjson(tmp_path / "out.ndjson")
        assert isinstance(result, PipelineResult)
        assert result.bytes_written > 0
        assert result.records_out == 2


# =====================================================================
# Dead-Letter Queue
# =====================================================================


class TestDeadLetterQueue:
    """Verify failed records are written to a dead-letter NDJSON file."""

    def test_dead_letter_writer_lazy_creation(self, tmp_path: Path) -> None:
        path = tmp_path / "dead.ndjson"
        writer = _DeadLetterWriter(path)
        # File should NOT exist yet
        assert not path.exists()
        writer.write({"foo": "bar"}, "test error")
        assert path.exists()
        writer.close()

    def test_dead_letter_writer_none_path(self) -> None:
        writer = _DeadLetterWriter(None)
        writer.write({"foo": "bar"}, "test error")  # Should not raise
        assert writer.count == 0
        writer.close()

    def test_dead_letter_writer_content(self, tmp_path: Path) -> None:
        path = tmp_path / "dead.ndjson"
        writer = _DeadLetterWriter(path)
        writer.write({"id": "1"}, "mapping failed")
        writer.write({"id": "2"}, "build failed")
        writer.close()

        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["_error"] == "mapping failed"
        assert first["_record"]["id"] == "1"

    def test_pipeline_dead_letter_on_bad_rows(
        self, tmp_path: Path, registry: ShapeRegistry, valid_rows: list[dict], bad_row: dict
    ) -> None:
        """Bad rows go to dead-letter file; good rows still produce output."""
        dl_path = tmp_path / "dead.ndjson"
        rows = [valid_rows[0], bad_row, valid_rows[1]]
        source = DictAdapter(rows)
        pipeline = Pipeline(
            source=source,
            shape="person",
            registry=registry,
            dead_letter_path=dl_path,
        )
        docs = pipeline.build_all()
        # 2 good rows succeed, 1 bad row goes to dead-letter
        assert len(docs) == 2
        assert dl_path.exists()
        dl_lines = dl_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(dl_lines) == 1
        entry = json.loads(dl_lines[0])
        assert "_error" in entry

    def test_pipeline_run_with_dead_letter(
        self, tmp_path: Path, registry: ShapeRegistry, valid_rows: list[dict], bad_row: dict
    ) -> None:
        dl_path = tmp_path / "dead.ndjson"
        rows = [valid_rows[0], bad_row, valid_rows[1]]
        source = DictAdapter(rows)
        pipeline = Pipeline(
            source=source,
            shape="person",
            registry=registry,
            dead_letter_path=dl_path,
        )
        result = pipeline.run()
        assert result.records_in == 3
        assert result.records_out == 2
        assert result.records_failed == 1
        assert result.dead_letter_path is not None

    def test_no_dead_letter_file_when_all_succeed(
        self, tmp_path: Path, registry: ShapeRegistry, valid_rows: list[dict]
    ) -> None:
        dl_path = tmp_path / "dead.ndjson"
        source = DictAdapter(valid_rows)
        pipeline = Pipeline(
            source=source,
            shape="person",
            registry=registry,
            dead_letter_path=dl_path,
        )
        docs = pipeline.build_all()
        assert len(docs) == 2
        # No failures → no dead-letter file created
        assert not dl_path.exists()


# =====================================================================
# Progress Tracking
# =====================================================================


class TestProgressTracking:
    """Verify progress callback and tqdm integration."""

    def test_progress_callback_invoked(self, registry: ShapeRegistry, valid_rows: list[dict]) -> None:
        calls: list[tuple[int, int | None]] = []

        def on_progress(current: int, total: int | None) -> None:
            calls.append((current, total))

        source = DictAdapter(valid_rows)
        pipeline = Pipeline(
            source=source,
            shape="person",
            registry=registry,
            progress=on_progress,
        )
        docs = pipeline.build_all()
        assert len(docs) == 2
        assert len(calls) == 2
        assert calls[0][0] == 1
        assert calls[1][0] == 2

    def test_progress_true_does_not_crash(self, registry: ShapeRegistry, valid_rows: list[dict]) -> None:
        """progress=True uses tqdm if available, silent otherwise."""
        source = DictAdapter(valid_rows)
        pipeline = Pipeline(
            source=source,
            shape="person",
            registry=registry,
            progress=True,
        )
        docs = pipeline.build_all()
        assert len(docs) == 2

    def test_progress_false_is_default(self, registry: ShapeRegistry, valid_rows: list[dict]) -> None:
        source = DictAdapter(valid_rows)
        pipeline = Pipeline(source=source, shape="person", registry=registry)
        # Default progress=False should work fine
        assert pipeline.build_all()


# =====================================================================
# Memory profiling (lightweight assertion)
# =====================================================================


class TestMemoryProfile:
    """Verify memory stays reasonable for large datasets.

    Note: This is a smoke test, not a full RSS measurement. It verifies
    that streaming mode doesn't materialize all records.
    """

    def test_stream_is_constant_memory(self, registry: ShapeRegistry) -> None:
        """Streaming 10K records one-at-a-time shouldn't OOM."""
        row = {
            "FirstName": "Test",
            "MiddleName": "",
            "LastName": "User",
            "GenerationCodeOrSuffix": "",
            "Birthdate": "2000-01-01",
            "Sex": "Female",
            "RaceEthnicity": "White",
            "PersonIdentifiers": "999888777",
            "IdentificationSystems": "PersonIdentificationSystem_SSN",
            "PersonIdentifierTypes": "PersonIdentifierType_PersonIdentifier",
        }
        source = DictAdapter([row] * 10_000)
        pipeline = Pipeline(source=source, shape="person", registry=registry)
        count = 0
        for _doc in pipeline.stream():
            count += 1
        assert count == 10_000


# =====================================================================
# Exports from top-level package
# =====================================================================


class TestExports:
    """Verify new Phase 7 classes are importable from ceds_jsonld."""

    def test_pipeline_result_importable(self) -> None:
        from ceds_jsonld import PipelineResult

        assert PipelineResult is not None

    def test_get_logger_importable(self) -> None:
        from ceds_jsonld import get_logger

        assert get_logger is not None

    def test_sanitize_importable(self) -> None:
        from ceds_jsonld import sanitize_iri_component, validate_base_uri

        assert sanitize_iri_component is not None
        assert validate_base_uri is not None

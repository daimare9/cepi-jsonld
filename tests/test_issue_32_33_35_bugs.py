"""Tests for issues #32, #33, and #35.

#32 — FieldMapper.compose() loses field metadata (datatype, optional, target)
#33 — PII masking mutates caller's original nested dicts/lists in-place
#35 — Pipeline.run() vs stream() raise different exception types
"""

from __future__ import annotations

import copy

import pytest

from ceds_jsonld.exceptions import MappingError, PipelineError
from ceds_jsonld.logging import _mask_pii, get_logger
from ceds_jsonld.mapping import FieldMapper


# ======================================================================
# Issue #32 — FieldMapper.compose() must deep-merge field metadata
# ======================================================================


class TestComposeFieldMetadataPreservation:
    """compose() must preserve base field metadata when overlay omits keys."""

    @pytest.fixture()
    def base_config(self) -> dict:
        return {
            "base_uri": "cepi:person/",
            "id_field": "PersonIdentifiers",
            "id_source": "PersonIdentifiers",
            "properties": {
                "hasPersonName": {
                    "fields": {
                        "first_name": {
                            "source": "FirstName",
                            "target": "FirstName",
                            "datatype": "xsd:string",
                            "optional": False,
                        },
                        "last_name": {
                            "source": "LastName",
                            "target": "LastOrSurname",
                            "datatype": "xsd:string",
                            "optional": False,
                        },
                    },
                },
            },
        }

    @pytest.fixture()
    def overlay_config(self) -> dict:
        return {
            "base_uri": "cepi:person/",
            "id_field": "PersonIdentifiers",
            "id_source": "PersonIdentifiers",
            "properties": {
                "hasPersonName": {
                    "fields": {
                        "first_name": {
                            "source": "FIRST_NM",
                        },
                    },
                },
            },
        }

    def test_overlay_source_is_applied(self, base_config, overlay_config):
        composed = FieldMapper.compose(base_config, overlay_config)
        field = composed.config["properties"]["hasPersonName"]["fields"]["first_name"]
        assert field["source"] == "FIRST_NM"

    def test_base_target_preserved(self, base_config, overlay_config):
        composed = FieldMapper.compose(base_config, overlay_config)
        field = composed.config["properties"]["hasPersonName"]["fields"]["first_name"]
        assert field["target"] == "FirstName"

    def test_base_datatype_preserved(self, base_config, overlay_config):
        composed = FieldMapper.compose(base_config, overlay_config)
        field = composed.config["properties"]["hasPersonName"]["fields"]["first_name"]
        assert field["datatype"] == "xsd:string"

    def test_base_optional_preserved(self, base_config, overlay_config):
        composed = FieldMapper.compose(base_config, overlay_config)
        field = composed.config["properties"]["hasPersonName"]["fields"]["first_name"]
        assert field["optional"] is False

    def test_untouched_field_unchanged(self, base_config, overlay_config):
        """Fields not mentioned in overlay must be completely untouched."""
        composed = FieldMapper.compose(base_config, overlay_config)
        field = composed.config["properties"]["hasPersonName"]["fields"]["last_name"]
        assert field == {
            "source": "LastName",
            "target": "LastOrSurname",
            "datatype": "xsd:string",
            "optional": False,
        }

    def test_overlay_adds_new_field(self, base_config):
        """A field present in overlay but absent from base must be added."""
        overlay = {
            "base_uri": "cepi:person/",
            "id_field": "PersonIdentifiers",
            "id_source": "PersonIdentifiers",
            "properties": {
                "hasPersonName": {
                    "fields": {
                        "suffix": {
                            "source": "Suffix",
                            "target": "GenerationCodeOrSuffix",
                            "optional": True,
                        },
                    },
                },
            },
        }
        composed = FieldMapper.compose(base_config, overlay)
        fields = composed.config["properties"]["hasPersonName"]["fields"]
        assert "suffix" in fields
        assert fields["suffix"]["target"] == "GenerationCodeOrSuffix"

    def test_compose_does_not_mutate_base(self, base_config, overlay_config):
        """compose() must not modify the base config dict."""
        snapshot = copy.deepcopy(base_config)
        FieldMapper.compose(base_config, overlay_config)
        assert base_config == snapshot


# ======================================================================
# Issue #33 — PII masking must not mutate caller's original data
# ======================================================================


class TestPIIMaskingNoMutation:
    """Logging with PII fields must never modify the caller's objects."""

    def test_mask_pii_does_not_mutate_flat(self):
        """Flat dict with PII key is not mutated."""
        original = {"ssn": "123-45-6789", "name": "Alice"}
        snapshot = copy.deepcopy(original)
        _mask_pii(original)
        assert original == snapshot

    def test_mask_pii_does_not_mutate_nested_dict(self):
        """Nested dict containing PII key is not mutated."""
        inner = {"ssn": "123-45-6789", "score": 95}
        outer = {"record": inner, "batch": 1}
        snapshot = copy.deepcopy(outer)
        _mask_pii(outer)
        assert outer == snapshot
        assert inner["ssn"] == "123-45-6789"

    def test_mask_pii_does_not_mutate_nested_list(self):
        """List containing dicts with PII keys is not mutated."""
        records = [{"firstname": "Alice"}, {"firstname": "Bob"}]
        outer = {"records": records}
        snapshot = copy.deepcopy(outer)
        _mask_pii(outer)
        assert outer == snapshot
        assert records[0]["firstname"] == "Alice"

    def test_mask_pii_returns_redacted_copy(self):
        """Returned dict has PII fields redacted."""
        original = {"ssn": "123-45-6789", "name": "Alice"}
        result = _mask_pii(original)
        assert result["ssn"] == "***REDACTED***"
        assert result["name"] == "Alice"

    def test_logger_info_does_not_mutate_kwargs(self):
        """Using get_logger().info() must not mutate the passed kwargs."""
        logger = get_logger("test_mutation")
        data = {"ssn": "111-22-3333", "value": 42}
        snapshot = copy.deepcopy(data)
        logger.info("test event", record=data)
        assert data == snapshot


# ======================================================================
# Issue #35 — Pipeline.run() must wrap errors in PipelineError
# ======================================================================


class TestPipelineExceptionConsistency:
    """Both run() and stream() must raise PipelineError for mapping failures."""

    def test_stream_raises_pipeline_error(self):
        """stream() wraps mapping failures in PipelineError."""
        from ceds_jsonld import Pipeline, ShapeRegistry
        from ceds_jsonld.adapters import DictAdapter

        registry = ShapeRegistry()
        registry.load_shape("person")

        bad_data = [{"FirstName": "Alice"}]
        adapter = DictAdapter(bad_data)
        pipeline = Pipeline(adapter, "person", registry)

        with pytest.raises(PipelineError):
            list(pipeline.stream())

    def test_run_raises_pipeline_error(self):
        """run() must also wrap mapping failures in PipelineError (not raw MappingError)."""
        from ceds_jsonld import Pipeline, ShapeRegistry
        from ceds_jsonld.adapters import DictAdapter

        registry = ShapeRegistry()
        registry.load_shape("person")

        bad_data = [{"FirstName": "Alice"}]
        adapter = DictAdapter(bad_data)
        pipeline = Pipeline(adapter, "person", registry)

        with pytest.raises(PipelineError):
            pipeline.run()

    def test_run_wraps_underlying_cause(self):
        """The PipelineError from run() must chain the original exception."""
        from ceds_jsonld import Pipeline, ShapeRegistry
        from ceds_jsonld.adapters import DictAdapter

        registry = ShapeRegistry()
        registry.load_shape("person")

        bad_data = [{"FirstName": "Alice"}]
        adapter = DictAdapter(bad_data)
        pipeline = Pipeline(adapter, "person", registry)

        with pytest.raises(PipelineError) as exc_info:
            pipeline.run()

        assert exc_info.value.__cause__ is not None

    def test_run_with_dlq_still_continues(self, tmp_path):
        """When dead_letter_path is set, run() should NOT raise — DLQ catches failures."""
        from ceds_jsonld import Pipeline, ShapeRegistry
        from ceds_jsonld.adapters import DictAdapter

        registry = ShapeRegistry()
        registry.load_shape("person")

        bad_data = [{"FirstName": "Alice"}]
        adapter = DictAdapter(bad_data)
        dlq = tmp_path / "dead.ndjson"
        pipeline = Pipeline(adapter, "person", registry, dead_letter_path=dlq)

        result = pipeline.run()
        assert result.records_failed >= 1
        assert result.records_out == 0

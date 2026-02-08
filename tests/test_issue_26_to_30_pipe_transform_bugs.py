"""Tests for issues #26–#30: pipe-handling, transform, and validation bugs.

Issue #26: Empty pipe segments create ghost sub-nodes with blank identifiers.
Issue #27: date_format transform is a no-op — any string becomes xsd:date.
Issue #28: race_prefix/sex_prefix produce bare trailing-underscore prefixes.
Issue #29: Mismatched pipe counts silently forward-fill last value.
Issue #30: Custom transforms returning None/non-string bypass validation.
"""

from __future__ import annotations

import pytest

from ceds_jsonld import DictAdapter, Pipeline, ShapeRegistry
from ceds_jsonld.exceptions import MappingError, PipelineError
from ceds_jsonld.transforms import date_format, first_pipe_split, race_prefix, sex_prefix
from ceds_jsonld.validator import PreBuildValidator, ValidationMode


@pytest.fixture()
def person_registry() -> ShapeRegistry:
    reg = ShapeRegistry()
    reg.load_shape("person")
    return reg


@pytest.fixture()
def base_row() -> dict[str, str]:
    return {
        "FirstName": "Jane",
        "LastName": "Doe",
        "Sex": "Female",
        "Birthdate": "2000-01-01",
        "PersonIdentifiers": "12345",
        "IdentificationSystems": "State",
    }


# -----------------------------------------------------------------------
# Issue #26 — Empty pipe segments
# -----------------------------------------------------------------------


class TestIssue26EmptyPipeSegments:
    """Empty pipe segments should not create ghost sub-nodes."""

    def test_first_pipe_split_empty_string_returns_none(self) -> None:
        assert first_pipe_split("") is None

    def test_first_pipe_split_leading_pipe_returns_none(self) -> None:
        assert first_pipe_split("|12345") is None

    def test_first_pipe_split_whitespace_returns_none(self) -> None:
        assert first_pipe_split("  ") is None

    def test_first_pipe_split_normal_value_works(self) -> None:
        assert first_pipe_split("111|222") == "111"

    def test_empty_middle_segment_skipped_in_pipeline(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        row = {**base_row, "PersonIdentifiers": "111||333", "IdentificationSystems": "State|Fed|Local"}
        pipe = Pipeline(DictAdapter([row]), "person", person_registry)
        docs = pipe.build_all()
        ident = docs[0]["hasPersonIdentification"]
        # Only 2 sub-nodes (111 and 333), the empty middle is skipped
        assert len(ident) == 2
        ids = [item["PersonIdentifier"]["@value"] for item in ident]
        assert "111" in ids
        assert "333" in ids

    def test_trailing_pipe_segment_skipped(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        row = {**base_row, "PersonIdentifiers": "111|222|", "IdentificationSystems": "State|Fed|Local"}
        pipe = Pipeline(DictAdapter([row]), "person", person_registry)
        docs = pipe.build_all()
        ident = docs[0]["hasPersonIdentification"]
        assert len(ident) == 2

    def test_validator_warns_on_empty_pipe_segments(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        row = {**base_row, "PersonIdentifiers": "111||333", "IdentificationSystems": "State|Fed|Local"}
        sd = person_registry.get_shape("person")
        validator = PreBuildValidator(sd.mapping_config)
        result = validator.validate_row(row, mode=ValidationMode.REPORT)
        assert result.warning_count > 0
        # Find the empty-segment warning
        all_issues = [issue for issues in result.issues.values() for issue in issues]
        messages = [i.message for i in all_issues]
        assert any("empty segments" in m.lower() for m in messages)


# -----------------------------------------------------------------------
# Issue #27 — date_format validation
# -----------------------------------------------------------------------


class TestIssue27DateFormat:
    """date_format must validate and normalize ISO 8601 dates."""

    def test_valid_iso_date_passes(self) -> None:
        assert date_format("2026-02-08") == "2026-02-08"

    def test_zero_pads_unpadded_date(self) -> None:
        assert date_format("2026-2-8") == "2026-02-08"

    def test_strips_time_component(self) -> None:
        assert date_format("2026-02-08T14:30:00") == "2026-02-08"

    def test_strips_datetime_with_space(self) -> None:
        assert date_format("2026-02-08 14:30:00") == "2026-02-08"

    def test_rejects_american_format(self) -> None:
        with pytest.raises(ValueError, match="not a valid ISO 8601 date"):
            date_format("02/08/2026")

    def test_rejects_plain_text(self) -> None:
        with pytest.raises(ValueError, match="not a valid ISO 8601 date"):
            date_format("yesterday")

    def test_rejects_impossible_date(self) -> None:
        with pytest.raises(ValueError, match="not a valid calendar date"):
            date_format("9999-99-99")

    def test_rejects_month_13(self) -> None:
        with pytest.raises(ValueError, match="not a valid calendar date"):
            date_format("2026-13-01")

    def test_rejects_feb_30(self) -> None:
        with pytest.raises(ValueError, match="not a valid calendar date"):
            date_format("2026-02-30")

    def test_pipeline_rejects_invalid_date(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        row = {**base_row, "Birthdate": "not-a-date"}
        pipe = Pipeline(DictAdapter([row]), "person", person_registry)
        # date_format raises ValueError → MappingError → PipelineError
        with pytest.raises(PipelineError, match="date_format.*not-a-date"):
            pipe.build_all()


# -----------------------------------------------------------------------
# Issue #28 — race_prefix / sex_prefix bare trailing underscore
# -----------------------------------------------------------------------


class TestIssue28PrefixEmpty:
    """Prefix transforms must return None for empty input."""

    def test_race_prefix_empty_returns_none(self) -> None:
        assert race_prefix("") is None

    def test_race_prefix_whitespace_returns_none(self) -> None:
        assert race_prefix("   ") is None

    def test_sex_prefix_empty_returns_none(self) -> None:
        assert sex_prefix("") is None

    def test_sex_prefix_whitespace_returns_none(self) -> None:
        assert sex_prefix("  ") is None

    def test_race_prefix_valid_input(self) -> None:
        assert race_prefix("White") == "RaceAndEthnicity_White"

    def test_sex_prefix_valid_input(self) -> None:
        assert sex_prefix("Female") == "Sex_Female"

    def test_trailing_pipe_no_ghost_race_node(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        row = {**base_row, "RaceEthnicity": "White|Asian|"}
        pipe = Pipeline(DictAdapter([row]), "person", person_registry)
        docs = pipe.build_all()
        race = docs[0].get("hasPersonDemographicRace", [])
        if isinstance(race, dict):
            race = [race]
        # Should only have 2 entries (White, Asian), not 3
        assert len(race) == 2
        for node in race:
            val = node.get("hasRaceAndEthnicity")
            assert val is not None, "Ghost race sub-node with None value detected"


# -----------------------------------------------------------------------
# Issue #29 — Mismatched pipe counts
# -----------------------------------------------------------------------


class TestIssue29PipeMismatch:
    """Mismatched pipe counts should not forward-fill."""

    def test_extra_segment_gets_none_not_forward_fill(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        row = {
            **base_row,
            "PersonIdentifiers": "AAA|BBB|CCC",
            "IdentificationSystems": "State|Fed",  # Only 2 segments
        }
        pipe = Pipeline(DictAdapter([row]), "person", person_registry)
        docs = pipe.build_all()
        ident = docs[0]["hasPersonIdentification"]

        # All 3 ID sub-nodes should exist
        assert len(ident) == 3

        # Third sub-node should NOT have IdentificationSystem = "Fed"
        third = ident[2]
        system = third.get("hasPersonIdentificationSystem")
        # System should be None/missing, not forward-filled to "Fed"
        assert system is None, (
            f"Expected no system for third ID (pipe mismatch), got {system!r}. "
            f"Forward-fill bug is still present."
        )

    def test_matched_pipe_counts_work_normally(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        row = {
            **base_row,
            "PersonIdentifiers": "AAA|BBB",
            "IdentificationSystems": "State|Fed",
        }
        pipe = Pipeline(DictAdapter([row]), "person", person_registry)
        docs = pipe.build_all()
        ident = docs[0]["hasPersonIdentification"]
        assert len(ident) == 2
        assert ident[0].get("hasPersonIdentificationSystem") == "State"
        assert ident[1].get("hasPersonIdentificationSystem") == "Fed"


# -----------------------------------------------------------------------
# Issue #30 — Post-transform validation
# -----------------------------------------------------------------------


class TestIssue30PostTransformValidation:
    """Transform results must be validated after execution."""

    def test_transform_returning_none_skips_field(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        pipe = Pipeline(
            DictAdapter([base_row]),
            "person",
            person_registry,
            custom_transforms={"nullify": lambda v: None},
            transform_overrides={"hasPersonName": {"FirstName": "nullify"}},
        )
        docs = pipe.build_all()
        name = docs[0]["hasPersonName"]
        # FirstName should be absent (None transform = skip), not literally None
        assert name.get("FirstName") is None or "FirstName" not in name

    def test_transform_returning_int_coerced_to_string(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        pipe = Pipeline(
            DictAdapter([base_row]),
            "person",
            person_registry,
            custom_transforms={"intify": lambda v: 42},
            transform_overrides={"hasPersonName": {"FirstName": "intify"}},
        )
        docs = pipe.build_all()
        name = docs[0]["hasPersonName"]
        # int should be coerced to str "42", not a raw int
        assert name.get("FirstName") == "42"
        assert isinstance(name.get("FirstName"), str)

    def test_transform_returning_dict_raises(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        pipe = Pipeline(
            DictAdapter([base_row]),
            "person",
            person_registry,
            custom_transforms={"dictify": lambda v: {"nested": "bad"}},
            transform_overrides={"hasPersonName": {"FirstName": "dictify"}},
        )
        with pytest.raises(PipelineError, match="returned a dict"):
            pipe.build_all()

    def test_transform_returning_list_raises(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        pipe = Pipeline(
            DictAdapter([base_row]),
            "person",
            person_registry,
            custom_transforms={"listify": lambda v: ["a", "b"]},
            transform_overrides={"hasPersonName": {"FirstName": "listify"}},
        )
        with pytest.raises(PipelineError, match="returned a sequence"):
            pipe.build_all()

    def test_transform_returning_bool_raises(
        self,
        person_registry: ShapeRegistry,
        base_row: dict[str, str],
    ) -> None:
        pipe = Pipeline(
            DictAdapter([base_row]),
            "person",
            person_registry,
            custom_transforms={"boolify": lambda v: True},
            transform_overrides={"hasPersonName": {"FirstName": "boolify"}},
        )
        with pytest.raises(PipelineError, match="returned a boolean"):
            pipe.build_all()

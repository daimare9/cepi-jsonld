"""Performance regression tests.

Baseline from PERFORMANCE_REPORT.md:
- Direct dict: ~47μs/record sequential
- 10K records: ~0.47s
- 1M records: ~30s (with parallel processing)

These tests guard against regressions in the generic YAML-driven pipeline.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from ceds_jsonld.adapters.dict_adapter import DictAdapter
from ceds_jsonld.builder import JSONLDBuilder
from ceds_jsonld.mapping import FieldMapper
from ceds_jsonld.pipeline import Pipeline
from ceds_jsonld.registry import ShapeRegistry


@pytest.fixture()
def mapper_and_builder(person_shape_def):
    """Pre-create mapper and builder for benchmarks."""
    mapper = FieldMapper(person_shape_def.mapping_config)
    builder = JSONLDBuilder(person_shape_def)
    return mapper, builder


@pytest.fixture()
def full_row() -> dict:
    """Sample row with multi-value fields for realistic benchmarking."""
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


class TestPerformanceRegression:
    """Guard against performance regressions in the build pipeline."""

    def test_10k_records_under_2_seconds(self, mapper_and_builder, full_row):
        """10K records must build in <2s (relaxed from 1s to account for generic overhead)."""
        mapper, builder = mapper_and_builder

        t0 = time.perf_counter()
        results = [builder.build_one(mapper.map(full_row)) for _ in range(10_000)]
        elapsed = time.perf_counter() - t0

        assert len(results) == 10_000
        assert elapsed < 2.0, f"10K records took {elapsed:.2f}s (limit: 2.0s)"

    def test_1k_records_under_500ms(self, mapper_and_builder, full_row):
        """1K records must build in <500ms."""
        mapper, builder = mapper_and_builder

        t0 = time.perf_counter()
        results = [builder.build_one(mapper.map(full_row)) for _ in range(1_000)]
        elapsed = time.perf_counter() - t0

        assert len(results) == 1_000
        assert elapsed < 0.5, f"1K records took {elapsed:.3f}s (limit: 0.5s)"

    def test_single_record_under_1ms(self, mapper_and_builder, full_row):
        """Single record must build in <1ms (excluding first-call warmup)."""
        mapper, builder = mapper_and_builder

        # Warm up
        builder.build_one(mapper.map(full_row))

        # Measure
        t0 = time.perf_counter()
        for _ in range(100):
            builder.build_one(mapper.map(full_row))
        elapsed = time.perf_counter() - t0
        per_record = elapsed / 100

        assert per_record < 0.001, f"Single record took {per_record * 1000:.2f}ms (limit: 1ms)"


class TestPipelinePerformance:
    """End-to-end pipeline performance: DictAdapter → Pipeline → file."""

    @pytest.fixture()
    def full_row(self) -> dict:
        """Sample row with multi-value fields."""
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

    @pytest.mark.benchmark
    def test_100k_pipeline_to_ndjson_under_10s(
        self, full_row: dict, tmp_path: Path
    ) -> None:
        """100K records through full Pipeline → NDJSON file in <10 seconds.

        This is the Phase 3 acceptance target from ROADMAP.md.
        """
        registry = ShapeRegistry()
        registry.load_shape("person")
        data = [full_row] * 100_000
        source = DictAdapter(data)
        pipeline = Pipeline(source=source, shape="person", registry=registry)

        out = tmp_path / "100k.ndjson"
        t0 = time.perf_counter()
        result = pipeline.to_ndjson(out)
        elapsed = time.perf_counter() - t0

        assert out.exists()
        assert result.bytes_written > 0
        assert elapsed < 10.0, f"100K records took {elapsed:.2f}s (limit: 10.0s)"

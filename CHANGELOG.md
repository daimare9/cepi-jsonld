# Changelog

All notable changes to this project will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR** — incompatible API changes
- **MINOR** — new features, backward-compatible
- **PATCH** — bug fixes, backward-compatible

Release cadence: **monthly** (first week of each month), with ad-hoc patch releases for critical fixes.

---

## [Unreleased]

*Nothing yet.*

---

## [0.9.5] — 2026-02-08

### Summary

Patch release fixing a flaky CI benchmark that caused the v0.9.4 main workflow to fail on Windows runners. No functional code changes. 526 tests passing.

### Fixed

- **Benchmarks** — Increased 100K pipeline performance test limits (15s base, 8× CI multiplier) to eliminate false failures on shared Windows CI runners

---

## [0.9.4] — 2026-02-08

### Summary

Patch release with 5 bug fixes hardening the pipeline against non-finite floats, booleans, None values, and empty lists across the mapper, builder, and serializer. 526 tests passing.

### Fixed

- **Pipeline** — `validate()` no longer double-counts errors and warnings; `add_issue()` already increments counters internally (#21)
- **Mapping** — `_ensure_scalar()` now rejects `bool` values and non-finite floats (`inf`, `-inf`, `nan`) with actionable error messages instead of silently coercing them to strings (#22)
- **Builder** — `_typed_literal()` returns `None` for `None`, `NaN`, and `Infinity` inputs instead of producing `@value: "None"` string literals; lists are filtered to remove non-finite entries (#23)
- **Builder** — `_build_sub_nodes()` guards against empty list values that previously caused `IndexError` on the single-element unwrap logic (#24)
- **Serializer** — `dumps()` now rejects `NaN`/`Infinity`/`-Infinity` floats with a `SerializationError` for both orjson and stdlib backends, preventing invalid JSON output (#25)

---

## [0.9.3] — 2026-02-08

### Summary

Patch release with 5 bug fixes for transform precision, adapter edge cases, and Pipeline DLQ reliability. 493 tests passing.

### Fixed

- **Transforms** — `first_pipe_split` avoids `float()` for pure-digit strings, preventing IEEE 754 precision loss on 16+ digit numeric IDs (#16)
- **Adapters** — `CSVAdapter.count()` skips blank lines and handles empty files (returns 0 instead of -1), matching `read()` behavior (#17)
- **Adapters** — `NDJSONAdapter` defaults to `utf-8-sig` encoding, transparently stripping UTF-8 BOM from Windows-exported files (#18)
- **Pipeline** — `to_json()` and `to_ndjson()` now properly track `records_failed` and `dead_letter_path` in `PipelineResult` (#19)
- **Pipeline** — Dead-letter writer uses fallback serialization (`repr()`/`default=str`) for non-JSON-serializable `raw_row` values like sets and datetimes (#20)

---

## [0.9.2] — 2026-02-08

### Summary

Patch release with 5 bug fixes covering validation counting, Cosmos DB preparation, serialization error handling, and PII masking. 471 tests passing.

### Fixed

- **Validator** — `PreBuildValidator.validate_batch()` and `SHACLValidator.validate_batch()` no longer double-count errors and warnings (#11)
- **Cosmos** — `prepare_for_cosmos()` uses `copy.deepcopy()` so nested objects are not shared between original and result (#12)
- **Cosmos** — `prepare_for_cosmos()` raises `CosmosError` for empty or slash-only `@id` values instead of silently producing an empty `id` (#13)
- **Serializer** — `dumps()` and `loads()` now wrap backend errors in `SerializationError`, matching `write_json()`/`read_json()` behaviour (#14)
- **Logging** — `_mask_pii()` recursively walks nested dicts/lists and detects SSN and email patterns in string values (#15)

---

## [0.9.1] — 2026-02-08

### Summary

Patch release with 8 bug fixes resolved from issue tracker. 456 tests passing.

### Fixed

- **Transforms** — `int_clean` no longer loses precision on large integers (>15 digits); uses `Decimal` path instead of `float()` (#5)
- **Transforms** — `int_clean` and `first_pipe_split` handle `Infinity`/`-Infinity`/`NaN` gracefully instead of crashing (#4)
- **Validator** — `PreBuildValidator` rejects impossible dates (`2026-02-30`), American format (`MM-DD-YYYY`), and non–zero-padded dates (#2, #3)
- **Mapping** — `FieldMapper` rejects falsy values (`0`, `False`, `None`, empty string) as document IDs with actionable error messages (#1)
- **Mapping** — `FieldMapper` rejects nested `dict`/`list` values in scalar fields instead of silently corrupting output (#6)
- **Sanitize** — `validate_base_uri()` enforces trailing `/` or `#` separator as its docstring claimed (#7)
- **Sanitize** — `sanitize_iri_component()` encodes path-traversal sequences (`../`, `..\`) and strips null bytes / control chars (#9, #10)
- **Data** — Bundled `person_sample.csv` regenerated with 90 unique `PersonIdentifiers` (was 20 unique across 90 rows) (#8)

### Added

- `Pipeline.build_all()` now logs a warning when duplicate `@id` values are detected in output
- Null-byte and control-character stripping in all string field values via `sanitize_string_value()`
- `sanitize_iri_component()` and `validate_base_uri()` hardened with path-traversal and injection protection

---

## [0.9.0] — 2026-02-07

### Summary

First public release. All core functionality complete across 7 development phases.
398 tests passing, 88% coverage.

### Added

- **Shape Registry** — Load and manage SHACL shape definitions with `ShapeRegistry.load_shape()`
- **Field Mapper** — Declarative YAML-driven column mapping with type coercion, transforms, and multi-value splitting
- **JSON-LD Builder** — High-performance direct-dict construction (161x faster than rdflib+PyLD)
- **SHACL Introspector** — Parse SHACL shapes into structured Python representations; generate mapping templates; validate mappings against SHACL constraints
- **Source Adapters** — 6 pluggable data sources:
  - `CSVAdapter` — CSV files (included)
  - `ExcelAdapter` — Excel .xlsx/.xls files (`pip install ceds-jsonld[excel]`)
  - `DictAdapter` — Python dicts (included)
  - `NDJSONAdapter` — Newline-delimited JSON (included)
  - `APIAdapter` — REST endpoints with pagination (`pip install ceds-jsonld[api]`)
  - `DatabaseAdapter` — SQL databases via SQLAlchemy (`pip install ceds-jsonld[database]`)
- **Pipeline** — High-level orchestrator connecting adapter → mapper → builder → output
  - `stream()` — constant-memory generator for large datasets
  - `build_all()` — batch processing
  - `to_json()` / `to_ndjson()` — file output
  - `to_cosmos()` — Azure Cosmos DB bulk loading
  - `validate()` — pre-build and SHACL validation
  - `PipelineResult` with throughput metrics
- **Validation** — Two-tier validation system:
  - `PreBuildValidator` — fast pure-Python schema checks (~0.01ms/record)
  - `SHACLValidator` — full pySHACL round-trip validation (~50ms/record)
  - Three modes: `strict`, `report`, `sample`
- **Cosmos DB Integration** — `CosmosLoader` with async bulk upsert, `prepare_for_cosmos()` utility, partition key management
- **CLI** — 6 commands: `convert`, `validate`, `introspect`, `generate-mapping`, `list-shapes`, `benchmark`
- **Serializer** — orjson backend (10x faster) with stdlib json fallback
- **Structured Logging** — structlog integration with PII masking (16 field patterns)
- **Dead-Letter Queue** — failed records written to NDJSON file for reprocessing
- **Progress Tracking** — tqdm + custom callback support
- **IRI Sanitization** — `sanitize_iri_component()` and `validate_base_uri()` for injection protection
- **Mapping Overrides** — `FieldMapper.with_overrides()` and `FieldMapper.compose()` for runtime column renaming
- **URI-Based Shape Fetching** — `ShapeRegistry.fetch_shape()` with local caching
- **Person shape** — Shipped as reference implementation with SHACL, context, mapping YAML, and sample data

### Shipped Shapes

- `person` — Person shape with PersonName, PersonBirth, PersonSexGender, PersonDemographicRace, PersonIdentification sub-shapes

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 0.9.5 | 2026-02-08 | Patch: fix flaky 100K benchmark on CI Windows runners. |
| 0.9.4 | 2026-02-08 | Patch: 5 bug fixes (non-finite floats, booleans, None handling, empty lists). |
| 0.9.3 | 2026-02-08 | Patch: 5 bug fixes (transform precision, adapter edges, DLQ reliability). |
| 0.9.2 | 2026-02-08 | Patch: 5 bug fixes (validation counting, Cosmos prep, serialization, PII). |
| 0.9.1 | 2026-02-08 | Patch: 8 bug fixes (validation, mapping, sanitization, sample data). |
| 0.9.0 | 2026-02-07 | First public release. All 7 phases complete. |

---

[Unreleased]: https://github.com/daimare9/ceds-jsonld/compare/v0.9.5...HEAD
[0.9.5]: https://github.com/daimare9/ceds-jsonld/compare/v0.9.4...v0.9.5
[0.9.4]: https://github.com/daimare9/ceds-jsonld/compare/v0.9.3...v0.9.4
[0.9.3]: https://github.com/daimare9/ceds-jsonld/compare/v0.9.2...v0.9.3
[0.9.2]: https://github.com/daimare9/ceds-jsonld/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/daimare9/ceds-jsonld/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/daimare9/ceds-jsonld/releases/tag/v0.9.0

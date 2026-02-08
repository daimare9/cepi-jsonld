# Changelog

All notable changes to this project will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR** — incompatible API changes
- **MINOR** — new features, backward-compatible
- **PATCH** — bug fixes, backward-compatible

Release cadence: **monthly** (first week of each month), with ad-hoc patch releases for critical fixes.

---

## [Unreleased]

*Nothing yet — next release will be 1.0.0.*

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
|---------|------|-----------|
| 0.9.0 | 2026-02-07 | First public release. All 7 phases complete. |

---

[Unreleased]: https://github.com/daimare9/cepi-jsonld/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/daimare9/cepi-jsonld/releases/tag/v0.9.0

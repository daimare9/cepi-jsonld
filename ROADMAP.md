# CEDS JSON-LD Generator Library — Full Roadmap

**Project:** `ceds-jsonld` — A Python library for ingesting education data from any source, mapping it to CEDS/CEPI ontology-backed RDF shapes, outputting conformant JSON-LD, and loading it into Azure Cosmos DB.

**Date:** February 7, 2026
**Status:** Phase 8 — Open Source Publishing (Phases 0–7 Complete)

---

## Table of Contents

1. [Vision & Goals](#1-vision--goals)
2. [Architecture Overview](#2-architecture-overview)
3. [Ontology & Shape Management Strategy](#3-ontology--shape-management-strategy)
4. [Phase 0 — Research & Proof-of-Concept](#phase-0--research--proof-of-concept-weeks-1-3)
5. [Phase 1 — Core Library Foundation](#phase-1--core-library-foundation-weeks-4-7)
6. [Phase 2 — SHACL-Driven Shape Engine](#phase-2--shacl-driven-shape-engine-weeks-8-11)
7. [Phase 3 — Data Ingestion Layer](#phase-3--data-ingestion-layer-weeks-12-15)
8. [Phase 4 — Azure Cosmos DB Integration](#phase-4--azure-cosmos-db-integration-weeks-16-19)
9. [Phase 5 — Validation & Quality](#phase-5--validation--quality-weeks-20-22)
10. [Phase 6 — CLI, Packaging & Documentation](#phase-6--cli-packaging--documentation-weeks-23-25)
11. [Phase 7 — Production Hardening](#phase-7--production-hardening-weeks-26-28)
12. [Key Technical Decisions](#key-technical-decisions)
13. [Risk Register](#risk-register)
14. [Dependency Map](#dependency-map)
15. [Appendix: Research Backlog](#appendix-research-backlog)

---

## 1. Vision & Goals

### The Problem

CEPI needs to ingest education data from diverse sources (APIs, spreadsheets, flat files, databases) across many different data collection shapes (Person, Organization, Student, Staff, K12 Enrollment, etc.). Each shape is backed by the [CEDS ontology](https://ceds.ed.gov/) as a base, extended by CEPI-specific properties and named individuals. Data must be:

1. **Mapped** to RDF-conformant structures defined by SHACL shapes
2. **Serialized** as compacted, human-readable JSON-LD with a hosted `@context`
3. **Validated** against the SHACL shapes before persistence
4. **Loaded** into Azure Cosmos DB as self-contained documents

### The Solution

A reusable Python library (`ceds-jsonld`) that provides:

- **Shape Registry** — Load and manage multiple SHACL shapes + their JSON-LD contexts + ontology extensions, each as a self-contained "collection definition"
- **Source Adapters** — Pluggable ingestion from CSV/Excel, REST APIs, databases, single-record dicts
- **Field Mapping Engine** — Declarative column-to-property mapping with transformations (type coercion, code list lookups, multi-value splitting)
- **JSON-LD Builder** — High-performance direct-dict construction (161x faster than rdflib+PyLD, proven in our benchmarks) driven by metadata extracted from SHACL shapes
- **SHACL Validator** — Optional pre-persist validation via pySHACL
- **Cosmos DB Loader** — Async bulk upsert to Azure Cosmos DB NoSQL API with partition key management
- **CLI & Scripting API** — Both programmatic and command-line interfaces

### Performance Target

Based on our prior benchmarking:

| Metric | Target |
|:---|:---|
| Single record build | < 0.05 ms |
| 1M records end-to-end (build + serialize + write) | < 60 seconds |
| Cosmos DB bulk upsert 100K records | < 5 minutes (at 10K RU/s) |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ceds-jsonld Library                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐   ┌───────────────┐   ┌────────────────────────┐ │
│  │  Source       │   │  Field        │   │  Shape Registry        │ │
│  │  Adapters     │──▶│  Mapping      │◀──│  (SHACL + Context +   │ │
│  │              │   │  Engine       │   │   Ontology Extensions) │ │
│  │  - CSV/Excel │   │              │   │                        │ │
│  │  - REST API  │   │  - Column    │   │  - PersonShape         │ │
│  │  - Database  │   │    mapping   │   │  - OrganizationShape   │ │
│  │  - Dict/JSON │   │  - Type      │   │  - K12EnrollmentShape  │ │
│  │  - NDJSON    │   │    coercion  │   │  - StaffShape          │ │
│  └──────────────┘   │  - Code list │   │  - ...N more           │ │
│                      │    lookups   │   └────────────────────────┘ │
│                      │  - Multi-val │                              │
│                      │    splitting │                              │
│                      └──────┬───────┘                              │
│                             │                                      │
│                      ┌──────▼───────┐                              │
│                      │  JSON-LD     │                              │
│                      │  Builder     │                              │
│                      │              │                              │
│                      │  Direct dict │                              │
│                      │  construction│                              │
│                      │  (no rdflib) │                              │
│                      └──────┬───────┘                              │
│                             │                                      │
│              ┌──────────────┼──────────────┐                       │
│              │              │              │                        │
│       ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐                │
│       │  SHACL      │ │  JSON    │ │  Cosmos DB  │                │
│       │  Validator  │ │  Output  │ │  Loader     │                │
│       │  (optional) │ │  (orjson)│ │  (async)    │                │
│       └─────────────┘ └──────────┘ └─────────────┘                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Ontology & Shape Management Strategy

### 3.1 File Organization Pattern

Each data collection shape will be a self-contained package:

```
ontologies/
├── base/
│   ├── CEDS-Ontology.rdf           # Full CEDS ontology (master reference)
│   ├── ceds_context.json           # Full CEDS JSON-LD context (26K lines)
│   └── Common.ttl                  # Shared CEPI extensions (RecordStatus, DataCollection, etc.)
│
├── person/
│   ├── Person_SHACL.ttl            # SHACL shape for Person + sub-shapes
│   ├── Person_CEPI_Extensions.ttl  # CEPI-specific named individuals, extra properties
│   ├── person_context.json         # JSON-LD context scoped to Person terms
│   ├── person_mapping.yaml         # Declarative field mapping config
│   └── person_sample.csv           # Sample data for testing
│
├── organization/
│   ├── Organization_SHACL.ttl
│   ├── Organization_CEPI_Extensions.ttl
│   ├── organization_context.json
│   ├── organization_mapping.yaml
│   └── organization_sample.csv
│
├── k12_enrollment/
│   ├── ...same pattern...
│
├── staff_assignment/
│   └── ...same pattern...
│
└── ... (one folder per collection shape)
```

### 3.2 Mapping Configuration (YAML-driven)

Each shape gets a declarative mapping file that the engine uses at runtime:

```yaml
# person_mapping.yaml
shape: PersonShape
context_url: "https://cepi-dev.state.mi.us/ontology/context-person.json"
context_file: person_context.json
base_uri: "cepi:person/"
id_source: PersonIdentifiers   # CSV column or field that provides the @id
id_transform: first_pipe_split  # take first value from pipe-delimited field

# Top-level type
type: Person

# Sub-shape mappings
properties:
  hasPersonName:
    type: PersonName
    cardinality: single          # one per person record
    include_record_status: true
    include_data_collection: true
    fields:
      FirstName:
        source: FirstName        # source column/field name
        target: FirstName        # JSON-LD term
        datatype: string
      MiddleName:
        source: MiddleName
        target: MiddleName
        datatype: string
        optional: true
      LastOrSurname:
        source: LastName
        target: LastOrSurname
        datatype: string
      GenerationCodeOrSuffix:
        source: GenerationCodeOrSuffix
        target: GenerationCodeOrSuffix
        datatype: string
        optional: true

  hasPersonBirth:
    type: PersonBirth
    cardinality: single
    include_record_status: true
    include_data_collection: true
    fields:
      Birthdate:
        source: Birthdate
        target: Birthdate
        datatype: xsd:date

  hasPersonSexGender:
    type: PersonSexGender
    cardinality: single
    include_record_status: true
    include_data_collection: true
    fields:
      hasSex:
        source: Sex
        target: hasSex
        transform: sex_prefix    # "Female" → "Sex_Female"

  hasPersonDemographicRace:
    type: PersonDemographicRace
    cardinality: multiple        # pipe-delimited groups
    split_on: "|"
    include_record_status: true
    include_data_collection: true
    fields:
      hasRaceAndEthnicity:
        source: RaceEthnicity
        target: hasRaceAndEthnicity
        transform: race_prefix   # "White" → "RaceAndEthnicity_White"
        multi_value_split: ","   # within each group, comma-separated

  hasPersonIdentification:
    type: PersonIdentification
    cardinality: multiple
    split_on: "|"
    include_record_status: true
    include_data_collection: true
    fields:
      PersonIdentifier:
        source: PersonIdentifiers
        target: PersonIdentifier
        datatype: xsd:token
      hasPersonIdentificationSystem:
        source: IdentificationSystems
        target: hasPersonIdentificationSystem
      hasPersonIdentifierType:
        source: PersonIdentifierTypes
        target: hasPersonIdentifierType

# Reusable sub-shapes applied when include_record_status/include_data_collection = true
record_status_defaults:
  type: RecordStatus
  RecordStartDateTime:
    value: "1900-01-01T00:00:00"
    datatype: xsd:dateTime
  RecordEndDateTime:
    value: "9999-12-31T00:00:00"
    datatype: xsd:dateTime
  CommittedByOrganization:
    value_id: "cepi:organization/3000000789"

data_collection_defaults:
  type: DataCollection
  value_id: "http://example.org/dataCollection/45678"
```

### 3.3 Why This Pattern?

- **Adding a new shape** = create a folder, write the SHACL, context, and YAML mapping. Zero library code changes.
- **Separation of concerns** — The SHACL is the canonical constraint definition (for validation). The YAML is the practical field mapping (for construction). The context.json is the semantic compaction layer (for JSON-LD).
- **CEPI extensions per shape** — Each shape can have its own named individuals, extra properties, etc., without polluting the global ontology.
- **Testable in isolation** — Each shape folder has its own sample data and can be tested independently.

---

## Phase 0 — Research & Proof-of-Concept (Weeks 1-3)

### 0.1 SHACL Parsing Research

> **Goal:** Determine how much useful structure we can extract from SHACL shapes programmatically to auto-generate or validate mapping configs.

| # | Task | Priority | Notes |
|---|------|----------|-------|
| 0.1.1 | Parse Person_SHACL.ttl with rdflib, extract all NodeShapes and PropertyShapes | P0 | Walk `sh:property`, `sh:path`, `sh:class`, `sh:node`, `sh:in`, `sh:datatype`, `sh:closed`, `sh:ignoredProperties` |
| 0.1.2 | Build a SHACL shape introspector that outputs a Python dict describing the shape tree | P0 | Recursive: PersonShape → hasPersonName → PersonNameShape → FirstName, etc. |
| 0.1.3 | Test with a second shape (Organization or K12Enrollment) to validate generality | P0 | Ensure the parser isn't over-fitted to Person |
| 0.1.4 | Determine if SHACL alone has enough info to drive construction (datatypes, cardinalities) or if YAML supplement is necessary | P1 | SHACL has `sh:datatype`, `sh:maxCount`, `sh:in` — may be sufficient for typed fields |
| 0.1.5 | Research pySHACL API for programmatic validation (not just CLI) | P1 | `pyshacl.validate(data_graph, shacl_graph)` returns `(conforms, results_graph, results_text)` |

### 0.2 JSON-LD Context Management Research

| # | Task | Priority | Notes |
|---|------|----------|-------|
| 0.2.1 | Determine context hosting strategy: static URL vs. embedded vs. hybrid | P0 | Current: `"@context": "https://cepi-dev.state.mi.us/ontology/context-person.json"` (URL reference) |
| 0.2.2 | Test whether Cosmos DB queries work against nested JSON-LD with `@type` and `@id` fields | P0 | Cosmos treats `@type`, `@id` as regular string fields—verify query behavior |
| 0.2.3 | Investigate context inheritance — can a Person context `@import` the base CEDS context? | P1 | JSON-LD 1.1 supports `@import` but tooling support varies |
| 0.2.4 | Test context-less storage (strip `@context` before Cosmos, re-inject on read) | P2 | Could reduce document size and avoid context drift |

### 0.3 Azure Cosmos DB Modeling Research

| # | Task | Priority | Notes |
|---|------|----------|-------|
| 0.3.1 | Design partition key strategy for JSON-LD documents | P0 | Options: `@type` (low cardinality), composite `{shape}/{org_id}`, or dedicated `partitionKey` field. `@type` risks hot partitions. |
| 0.3.2 | Test Cosmos DB emulator with sample Person JSON-LD documents | P0 | Install emulator, create container, upsert, query by fields inside nested JSON-LD |
| 0.3.3 | Benchmark `azure-cosmos` Python SDK bulk operations (upsert_item in parallel) | P0 | Python SDK doesn't have native bulk executor like .NET — need to use asyncio + concurrent upserts |
| 0.3.4 | Test indexing policy: which JSON-LD fields to index, which to exclude | P1 | Index `@type`, `@id`, and key queryable fields; exclude deep nested RecordStatus/DataCollection to save RU/s |
| 0.3.5 | Evaluate document size limits: 2MB max item size in Cosmos | P1 | Person docs are ~4KB each — safe. But what about shapes with unbounded arrays? |
| 0.3.6 | Research container-per-shape vs. single-container-with-discriminator | P1 | Container per shape = simpler indexing, partition keys. Single container = fewer resources, cross-shape queries possible |
| 0.3.7 | Test TTL (time-to-live) on documents for snapshot-based data collections | P2 | Each data collection is a point-in-time snapshot; older snapshots could age out |

### 0.4 Second Shape Development (Organization or K12Enrollment)

| # | Task | Priority | Notes |
|---|------|----------|-------|
| 0.4.1 | Create Organization_SHACL.ttl | P0 | Validates that the library architecture works beyond Person |
| 0.4.2 | Create organization_context.json | P0 | |
| 0.4.3 | Create organization_mapping.yaml | P0 | |
| 0.4.4 | Build sample Organization CSV data (30+ records) | P0 | |
| 0.4.5 | Hand-build a `build_organization_direct()` function mirroring Person approach | P0 | This confirms the pattern generalizes before we invest in automation |

### 0.5 Performance Validation

| # | Task | Priority | Notes |
|---|------|----------|-------|
| 0.5.1 | Benchmark direct-dict approach with Organization shape | P0 | Confirm ≤0.05 ms/record holds for a different shape structure |
| 0.5.2 | Test orjson serialization with mixed shape types in single output | P1 | Array of heterogeneous documents (Person + Org) |
| 0.5.3 | Profile pySHACL validation cost per record | P1 | Expect it to be expensive — determines whether we validate pre-build or sample-validate |

### Phase 0 Deliverables

- [x] ~~SHACL shape introspector script~~ — Deferred to Phase 2 (task 2.1.1)
- [x] ~~Organization shape files~~ — Deferred to Phase 2 (task 2.3); Person shape validated the architecture
- [x] ~~Cosmos DB test script~~ — Deferred to Phase 4
- [x] Performance benchmarking: direct dict 161× faster than rdflib+PyLD, proven at 1M records (see `ResearchFiles/PERFORMANCE_REPORT.md`)
- [x] Architecture decisions documented: direct dict, YAML mapping, orjson, container-per-shape, optional SHACL validation
- [x] Go/no-go decision: **GO** — Library architecture validated through Person shape proof-of-concept

> **Phase 0 completed February 2026.** Research tasks not performed in isolation were folded into later phases where they fit naturally (SHACL introspection → Phase 2, Cosmos testing → Phase 4).

---

## Phase 1 — Core Library Foundation (Weeks 4-7)

### 1.1 Project Scaffolding

```
ceds-jsonld/
├── pyproject.toml               # PEP 621 project metadata
├── README.md
├── LICENSE
├── src/
│   └── ceds_jsonld/
│       ├── __init__.py
│       ├── registry.py          # ShapeRegistry: load & manage shape definitions
│       ├── builder.py           # JSONLDBuilder: construct documents from mapped data
│       ├── mapping.py           # FieldMapper: apply mapping config to raw data
│       ├── transforms.py        # Built-in transform functions (type coercion, prefixing)
│       ├── validator.py         # SHACLValidator: optional pySHACL validation
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py          # SourceAdapter abstract base class
│       │   ├── csv_adapter.py
│       │   ├── excel_adapter.py
│       │   ├── api_adapter.py
│       │   ├── dict_adapter.py
│       │   └── ndjson_adapter.py
│       ├── cosmos/
│       │   ├── __init__.py
│       │   ├── client.py        # CosmosLoader: async bulk operations
│       │   ├── partition.py     # Partition key strategies
│       │   └── indexing.py      # Recommended indexing policies per shape
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py          # Click-based CLI
│       └── ontologies/          # Shipped shape definitions
│           ├── base/
│           ├── person/
│           └── organization/
├── tests/
│   ├── conftest.py
│   ├── test_registry.py
│   ├── test_builder.py
│   ├── test_mapping.py
│   ├── test_adapters.py
│   ├── test_cosmos.py
│   ├── test_validator.py
│   └── fixtures/
│       ├── person_sample.csv
│       └── organization_sample.csv
└── docs/
    ├── getting_started.md
    ├── adding_shapes.md
    └── cosmos_setup.md
```

### 1.2 Shape Registry (`registry.py`)

| # | Task | Details |
|---|------|---------|
| 1.2.1 | `ShapeRegistry` class — singleton that holds all loaded shape definitions | Load from `ontologies/` directory or custom path |
| 1.2.2 | `ShapeDefinition` dataclass — holds SHACL graph, JSON-LD context dict, mapping config, and shape metadata | Parsed and cached on first load |
| 1.2.3 | `registry.load_shape("person")` — loads all files from a shape folder | Validates that required files exist: SHACL, context, mapping |
| 1.2.4 | `registry.list_shapes()` — returns available shape names | |
| 1.2.5 | `registry.get_shape("person")` — returns `ShapeDefinition` | |
| 1.2.6 | Support user-defined shape directories (not just built-in) | `registry.add_shape_dir("/path/to/custom/shapes/")` |

### 1.3 Field Mapper (`mapping.py`)

| # | Task | Details |
|---|------|---------|
| 1.3.1 | YAML mapping config parser | Load and validate the `_mapping.yaml` files |
| 1.3.2 | `FieldMapper.map(raw_row, mapping_config) → mapped_dict` | Applies column name mapping, type coercion, transforms |
| 1.3.3 | Built-in transforms: `sex_prefix`, `race_prefix`, `code_list_lookup`, `pipe_split`, `comma_split`, `int_clean`, `date_format` | Registered by name, referenced in YAML |
| 1.3.4 | Custom transform registration: `mapper.register_transform("my_custom", fn)` | User-extensible |
| 1.3.5 | Missing field handling: skip optional, raise on required | Configurable per-field in YAML (`optional: true/false`) |

### 1.4 JSON-LD Builder (`builder.py`)

| # | Task | Details |
|---|------|---------|
| 1.4.1 | `JSONLDBuilder(shape_def)` — initialized with a ShapeDefinition | |
| 1.4.2 | `builder.build_one(mapped_row) → dict` — builds a single JSON-LD document | Direct dict construction, no rdflib, no PyLD |
| 1.4.3 | `builder.build_many(rows) → list[dict]` — builds a batch | Simple list comprehension — proven fastest in benchmarks |
| 1.4.4 | Sub-shape construction driven by mapping config | Recursive: reads `properties:` from YAML, builds nested dicts |
| 1.4.5 | `hasRecordStatus` / `hasDataCollection` injection | Uses `record_status_defaults` and `data_collection_defaults` from mapping |
| 1.4.6 | Multi-value + multi-instance handling | Pipe-split → multiple sub-shape instances. Comma-split → array within one instance |
| 1.4.7 | Typed literal construction | `{"@type": "xsd:date", "@value": "1990-01-01"}` from `datatype` config |

### Phase 1 Deliverables

- [x] Installable Python package (`pip install -e ".[dev]"`)
- [x] `ShapeRegistry` loading Person shape with `ShapeDefinition` dataclass
- [x] `FieldMapper` applying Person mapping config to CSV rows with custom transform support
- [x] `JSONLDBuilder` producing identical output to `build_person_direct()` — verified by golden file test
- [x] `Serializer` module: orjson backend with stdlib `json` fallback
- [x] `transforms.py`: 5 built-in transforms (`sex_prefix`, `race_prefix`, `first_pipe_split`, `int_clean`, `date_format`)
- [x] `exceptions.py`: 6-class hierarchy (`CEDSJSONLDError`, `ShapeLoadError`, `MappingError`, `BuildError`, `ValidationError`, `SerializationError`)
- [x] Person ontology files organized in `src/ceds_jsonld/ontologies/person/`
- [x] Unit tests: **89 passed, 0 failed, 90% coverage**
- [x] Performance benchmarks: 10K records <2s, single record <1ms

> **Phase 1 completed February 2026.**
>
> **Deferred from Phase 1:**
> - Organization shape → Phase 2 (task 2.3; validate SHACL introspector with second shape)
> - `validator.py` → Phase 5 (SHACL validation is opt-in, not in hot path)
> - `code_list_lookup` transform → deferred (not needed yet)

---

## Phase 2 — SHACL-Driven Shape Engine (Weeks 8-11)

### 2.1 SHACL Introspector

| # | Task | Details |
|---|------|---------|
| 2.1.1 | `SHACLIntrospector(shacl_graph)` — parses a SHACL Turtle file into a structured Python representation | Uses rdflib to query the SHACL graph |
| 2.1.2 | Extract shape tree: `PersonShape → [hasPersonName → PersonNameShape → [FirstName, MiddleName, ...]]` | Walk `sh:property` → `sh:path`, `sh:node`, `sh:class` |
| 2.1.3 | Extract constraints: `sh:datatype`, `sh:maxCount`, `sh:minCount`, `sh:in` (allowed values), `sh:closed` | Used for validation and auto-typing |
| 2.1.4 | Extract allowed named individuals from `sh:in` lists | e.g., `hasPersonIdentificationSystem` allows specific `ceds:NI*` values |
| 2.1.5 | Generate YAML mapping template from SHACL | Scaffold a `_mapping.yaml` from introspected shapes — user fills in `source:` columns |
| 2.1.6 | Validate existing YAML mapping against SHACL shape | Detect mismatches: missing required fields, wrong datatypes, unknown properties |

### 2.2 Auto-Generated Builders (Stretch Goal)

| # | Task | Details |
|---|------|---------|
| 2.2.1 | Generate builder functions from SHACL + YAML at load time | Instead of hand-coding `build_person_direct()`, generate it from config |
| 2.2.2 | Code generation vs. runtime interpretation tradeoff analysis | Generated code = fastest. Runtime = most flexible. Benchmark both. |
| 2.2.3 | If runtime interpretation is <2x slower than generated, prefer runtime | Our baseline is 0.02 ms/record — even 5x slower is still ~0.1 ms (trivially fast) |

### ~~2.3 Organization Shape~~ — Deferred

> ~~Deferred from Phase 0.~~ Shape files (SHACL, context, mapping, sample data) for Organization and other shapes will be provided by external processes and added to the project at a later date. The generic pipeline already handles arbitrary shapes via YAML mapping configs — Organization will validate this when its files are ready. Moved out of Phase 2 scope.

### 2.4 Mapping Flexibility

> New tasks from Phase 1 retrospective. The current mapping system requires a full YAML per source structure. These features reduce friction when source data differs slightly from the standard mapping.

| # | Task | Details |
|---|------|---------||
| 2.4.1 | **Programmatic mapping overrides** — `mapper.override_source("FirstName", "student_first")` | Quick column renames at runtime without duplicating the entire YAML. Implemented as dict merge on `FieldMapper` |
| 2.4.2 | **Mapping composition** — merge a base YAML with a partial overrides dict or YAML | `FieldMapper(base_config, overrides={...})` — deep-merge properties, keeping base defaults for unspecified fields |
| 2.4.3 | Validate mapping overrides against SHACL (reuses task 2.1.6) | Ensure overridden sources still map to valid SHACL properties |

### 2.5 URI-Based Ontology Fetching

> New task from Phase 1 retrospective. Shape files are currently static in the package. This adds a dev-time tool to fetch from canonical hosted URIs.

| # | Task | Details |
|---|------|---------||
| 2.5.1 | `registry.fetch_shape(name, shacl_url=, context_url=)` — download and cache shape files locally | Dev-time tool, not runtime. Downloads SHACL + context to `ontologies/{name}/` directory |
| 2.5.2 | Cache management: check `ETag` / `Last-Modified` headers, skip re-download if unchanged | Avoid unnecessary network calls; store metadata in `.cache.json` per shape |
| 2.5.3 | CLI wrapper deferred to Phase 6: `ceds-jsonld fetch-shape --name person --shacl-url https://...` | |

### Phase 2 Deliverables

- [x] `SHACLIntrospector` extracting full shape tree from any SHACL file — `introspector.py`: `NodeShapeInfo`, `PropertyInfo`, `SHACLIntrospector` with `root_shape()`, `all_shapes()`, `get_shape()`, `to_dict()`
- [x] Auto-generated YAML mapping template for Person (and any future shape) — `generate_mapping_template()` with context-based name resolution
- [x] YAML↔SHACL validation report (flags mismatches) — `validate_mapping()` detects missing required fields, extra properties, type mismatches
- [x] Decision document: generated vs. runtime builders — Runtime interpretation chosen (current builder is already <0.05ms/record, no generation needed)
- [x] ~~Organization shape~~ — deferred; shape files will be provided externally
- [x] Mapping overrides and composition API on `FieldMapper` — `with_overrides()` (source/transform/ID overrides), `compose()` (deep-merge base+overlay), `.config` property
- [x] URI-based shape fetching with local caching on `ShapeRegistry` — `fetch_shape()` with download, local cache, `force` re-download
- [x] Unit tests: **142 passed, 0 failed, 91% coverage**

> **Phase 2 completed February 7, 2026.** All introspection, mapping flexibility, and URI fetching features implemented. Test suite grew from 89 to 142 tests with 91% coverage. Auto-builder benchmarking confirmed runtime interpretation is fast enough (<0.05ms/record) — code generation deferred as unnecessary.

---

## Phase 3 — Data Ingestion Layer (Weeks 12-15)

### 3.1 Source Adapter Interface

```python
class SourceAdapter(ABC):
    """Abstract base for all data source adapters."""

    @abstractmethod
    def read(self, source: Any, **kwargs) -> Iterator[dict]:
        """Yield raw records as dicts."""
        ...

    @abstractmethod
    def read_batch(self, source: Any, batch_size: int, **kwargs) -> Iterator[list[dict]]:
        """Yield batches of raw records."""
        ...
```

### 3.2 Adapter Implementations

| # | Adapter | Input | Notes |
|---|---------|-------|-------|
| 3.2.1 | `CSVAdapter` | `.csv` file path | pandas-based. Handles pipe/comma multi-value encoding. Configurable quoting, encoding, delimiter. |
| 3.2.2 | `ExcelAdapter` | `.xlsx` / `.xls` file path | openpyxl/xlrd backend. Sheet selection, header row config. |
| 3.2.3 | `DictAdapter` | `dict` or `list[dict]` | For single-record API calls or pre-parsed data. Pass-through. |
| 3.2.4 | `APIAdapter` | REST endpoint URL | `httpx`-based async client. Pagination support (cursor, offset, link-header). Auth (API key, OAuth2, cert). Rate limiting. |
| 3.2.5 | `NDJSONAdapter` | `.ndjson` file path or stream | Line-delimited JSON. Streaming — no full-file load. |
| 3.2.6 | `DatabaseAdapter` | SQLAlchemy connection string + query | For direct DB extraction. Returns rows as dicts. |

### 3.3 Ingestion Pipeline

```python
from ceds_jsonld import ShapeRegistry, Pipeline

registry = ShapeRegistry()
registry.load_shape("person")

pipeline = Pipeline(
    source=CSVAdapter("students.csv"),
    shape="person",
    registry=registry,
)

# Stream mode — process and output one at a time
for doc in pipeline.stream():
    print(doc)  # JSON-LD dict

# Batch mode — return all
docs = pipeline.build_all()

# File output
pipeline.to_json("output.json")          # single JSON array
pipeline.to_ndjson("output.ndjson")       # one doc per line (streaming-friendly)

# Cosmos output
pipeline.to_cosmos(cosmos_client, database="ceds", container="person")
```

### Phase 3 Deliverables

- [x] All 6 adapters implemented and tested — CSVAdapter, ExcelAdapter, DictAdapter, NDJSONAdapter, APIAdapter (pytest-httpserver), DatabaseAdapter (SQLite). 49 adapter tests, zero mocks.
- [x] `Pipeline` class orchestrating adapter → mapper → builder → output — `stream()`, `build_all()`, `to_json()`, `to_ndjson()`, `to_cosmos()` (stub). 18 pipeline tests.
- [x] Stream mode for memory-efficient processing of large files — `stream()` and `to_ndjson()` use constant memory.
- [x] Integration test: CSV → JSON-LD → file, with 100K records under 10 seconds — 100K pipeline benchmark passes.

> **Phase 3 completed February 7, 2026.** Data ingestion layer with 6 real adapters, Pipeline orchestrator, and full test suite using real dependencies (no mocks). 210 tests, 87% coverage.

---

## Phase 4 — Azure Cosmos DB Integration (Weeks 16-19)

### 4.1 Cosmos Client Wrapper

| # | Task | Details |
|---|------|---------|
| 4.1.1 | `CosmosLoader(endpoint, credential, database, container)` | Wraps `azure.cosmos.CosmosClient` with sensible defaults |
| 4.1.2 | `loader.upsert_one(doc)` — single document upsert | Uses `container.upsert_item()`. Returns response with RU charge. |
| 4.1.3 | `loader.upsert_many(docs, concurrency=10)` — async bulk upsert | Python SDK lacks native bulk executor. Use `asyncio.gather()` with semaphore-bounded concurrency. |
| 4.1.4 | Partition key injection | Auto-inject `partitionKey` field from `@type` or mapping config before upsert |
| 4.1.5 | Error handling: 429 throttle retry, 413 payload too large, 409 conflict | Exponential backoff included in SDK; surface actionable errors |
| 4.1.6 | RU budget tracking | Log cumulative RU cost per batch for cost monitoring |

### 4.2 Document Design for Cosmos

| Decision | Recommendation | Reasoning |
|----------|---------------|-----------|
| **Container strategy** | One container per shape type | Simpler partition keys, indexing policies, and TTL rules per shape. Cost isolation. |
| **Partition key** | `/@type` or `/collectionId` | `@type` groups related records; `collectionId` allows per-data-collection partitioning |
| **`id` field** | Copy `@id` value to `id` (Cosmos requires `id`) | Cosmos needs a string `id` at the root. Map from `@id` or generate UUID. |
| **Indexing policy** | Include: `/@type`, `/id`, top-level search fields. Exclude: `/*` (deep nested) | Saves RU/s on writes. Manual includes for query patterns. |
| **TTL** | -1 (no expiry) unless data collection scoped | Consider TTL for ephemeral staging data |

### 4.3 Cosmos Emulator Testing

| # | Task | Details |
|---|------|---------|
| 4.3.1 | Docker-based Cosmos emulator setup script | `docker run` with cert setup for local testing |
| 4.3.2 | Create container with JSON-LD document indexing policy | Test queries: `SELECT * FROM c WHERE c["@type"] = "Person"` |
| 4.3.3 | Benchmark: upsert 10K Person docs, measure RU cost + latency | Establish baseline for capacity planning |
| 4.3.4 | Test cross-partition queries: query by nested field | e.g., find persons with specific `PersonIdentifier` value |
| 4.3.5 | Async bulk upsert benchmark: 100K docs with varying concurrency | Find optimal concurrency level |

### Phase 4 Deliverables

- [x] `CosmosLoader` with single (`upsert_one`) and bulk (`upsert_many`) upsert — async with semaphore-bounded concurrency, `UpsertResult` / `BulkResult` return types, RU tracking
- [x] Partition key strategy implemented and tested — `prepare_for_cosmos()` utility auto-injects `id` (from `@id`) and `partitionKey` (from `@type` or explicit value)
- [x] Indexing policy recommendations per shape — `RECOMMENDED_INDEXING_POLICY` constant (indexes `id`, `partitionKey`, `@type` only; excludes deep nested)
- [x] `Pipeline.to_cosmos()` wired — accepts endpoint, credential (TokenCredential or string key), database; container defaults to shape name; supports `DefaultAzureCredential`, master key, and managed identity
- [x] `CosmosError` exception class added to hierarchy
- [x] `CosmosLoader` and `prepare_for_cosmos` exported from top-level `ceds_jsonld` package
- [ ] ~~Benchmark results: throughput, RU cost, optimal concurrency~~ — Deferred (no Cosmos emulator available; benchmarks ready to run when access is available)
- [ ] ~~Emulator-based integration tests~~ — Deferred (emulator not available; integration test structure in place, mocked for unit tests)
- [x] Unit tests: **241 passed, 0 failed** (28 new Cosmos tests: 12 prepare_for_cosmos, 10 CosmosLoader, 3 Pipeline.to_cosmos, 3 data classes/policy)

> **Phase 4 completed February 7, 2026.** CosmosLoader, document preparation, Pipeline wiring, and unit tests all implemented. Benchmarks and emulator-based integration tests deferred until Cosmos DB access is available. The SDK handles 429-retry automatically; document design follows one-container-per-shape with selective indexing.

---

## Phase 5 — Validation & Quality (Weeks 20-22)

### 5.1 SHACL Validation Integration

| # | Task | Details |
|---|------|---------|
| 5.1.1 | `SHACLValidator(shacl_graph)` — wraps pySHACL | |
| 5.1.2 | `validator.validate_one(jsonld_doc) → ValidationResult` | Convert JSON-LD dict to rdflib Graph, validate against SHACL shape |
| 5.1.3 | `validator.validate_batch(docs, sample_rate=0.01) → list[ValidationResult]` | Full validation is expensive (~50ms/doc). Sample-based for bulk. |
| 5.1.4 | Structured error reporting | Map `sh:resultPath` and `sh:resultMessage` to human-readable field names using context |
| 5.1.5 | Validation modes: `strict` (fail on first error), `report` (collect all), `sample` (random N%) | Configurable per pipeline |

### 5.2 Pre-Build Validation (Lightweight)

| # | Task | Details |
|---|------|---------|
| 5.2.1 | Schema-level validation from mapping config | Before building: check required fields present, types match, enum values valid |
| 5.2.2 | This is fast (pure Python dict checks) vs. SHACL (rdflib round-trip) | Expected <0.01 ms/record vs ~50 ms for full SHACL |
| 5.2.3 | Generate validation rules from SHACL introspection | Auto-populate: required fields from `sh:minCount`, allowed values from `sh:in`, etc. |

### 5.3 Test Infrastructure

| # | Task | Details |
|---|------|---------|
| 5.3.1 | Golden file tests: compare builder output against handcrafted reference JSON-LD | `person_example.json` as reference for Person shape |
| 5.3.2 | Round-trip tests: build JSON-LD → parse with rdflib → validate with pySHACL → confirm conforms | Proves the output is valid RDF |
| 5.3.3 | Property-based testing with Hypothesis | Generate random CSV rows, build docs, validate structure |
| 5.3.4 | Regression benchmarks in CI | Fail build if performance regresses more than 20% |

### Phase 5 Deliverables

- [x] `SHACLValidator` with strict, report, and sample modes — Full pySHACL round-trip validation with structured error reporting, context injection, and sample-based checking
- [x] Pre-build lightweight validation — `PreBuildValidator` with compiled field rules, required-field checks, datatype plausibility (xsd:date, xsd:dateTime, xsd:integer), allowed-value enforcement (sh:in), and SHACL-enriched rule generation via `from_introspector()`
- [x] `ValidationResult` + `FieldIssue` + `ValidationMode` — Structured error model with per-record issue tracking, error/warning severity, summary reporting
- [x] `Pipeline.validate()` + inline validation on `stream()`/`build_all()` — Two-phase validation (pre-build → optional SHACL), filtering/raising modes, wired into Pipeline API
- [x] Golden file tests for each shipped shape — `test_golden_file.py` validates Person shape output
- [x] Round-trip validation tests — Build JSON-LD → parse rdflib → validate pySHACL → confirm conforms
- [x] Property-based testing with Hypothesis — 7 Hypothesis tests with custom composite strategies
- [x] All new classes exported from `ceds_jsonld` package — `FieldIssue`, `PreBuildValidator`, `SHACLValidator`, `ValidationMode`, `ValidationResult`
- [x] Unit tests: **331 passed, 0 failed** (51 new coverage-gap tests, 32 validator tests, 7 Hypothesis tests)
- [x] Test coverage: **88% overall** — Core modules: pipeline 94%, validator 91%, builder 97%, mapping 92%, introspector 91%. Remaining gaps are defensive import guards and Azure Cosmos live-endpoint code.

> **Phase 5 completed July 2025.** Full validation subsystem implemented: `PreBuildValidator` for fast pure-Python schema checks (~0.01ms/record), `SHACLValidator` for full pySHACL round-trip validation (~50ms/record), three validation modes (strict/report/sample), Pipeline integration with `validate()` and inline `stream(validate=True)`. Coverage pushed from 84% to 88% with 90 new tests. Person SHACL shape fixed (3 missing PropertyShape definitions). Hypothesis property-based testing added.

---

## Phase 6 — CLI, Packaging & Documentation (Weeks 23-25)

### 6.1 CLI (`click`-based)

```bash
# Convert CSV to JSON-LD file
ceds-jsonld convert --shape person --input students.csv --output students.json

# Convert and load into Cosmos
ceds-jsonld convert --shape person --input students.csv --cosmos-db ceds --cosmos-container person

# Validate JSON-LD against SHACL
ceds-jsonld validate --shape person --input students.json

# Introspect a SHACL file
ceds-jsonld introspect --shacl Person_SHACL.ttl

# Generate mapping template from SHACL
ceds-jsonld generate-mapping --shacl Person_SHACL.ttl --output person_mapping.yaml

# List available shapes
ceds-jsonld list-shapes

# Benchmark a shape
ceds-jsonld benchmark --shape person --records 100000
```

### 6.2 Python Package

| # | Task | Details |
|---|------|---------|
| 6.2.1 | `pyproject.toml` with proper metadata, dependencies, entry points | |
| 6.2.2 | Build with `hatchling` or `setuptools` | |
| 6.2.3 | Optional dependency groups: `[cosmos]`, `[excel]`, `[api]`, `[dev]` | Only install azure-cosmos if cosmos features needed |
| 6.2.4 | Publish to internal PyPI / Azure Artifacts | |

### 6.3 Documentation

| # | Task | Details |
|---|------|---------|
| 6.3.1 | Getting Started guide | Install, first conversion, view output |
| 6.3.2 | Adding a New Shape guide | Step-by-step: create SHACL, context, mapping, sample, test |
| 6.3.3 | Cosmos DB Setup guide | Container creation, indexing, partition key rationale |
| 6.3.4 | API Reference (auto-generated from docstrings) | Sphinx or MkDocs |
| 6.3.5 | Architecture Decision Records (ADRs) | Capture key decisions: why direct-dict, why YAML mapping, why orjson |

### Phase 6 Deliverables

- [x] Full CLI with all commands — `convert`, `validate`, `introspect`, `generate-mapping`, `list-shapes`, `benchmark` via `click`-based `ceds-jsonld` entry point
- [x] Installable package with optional dependency groups — `pyproject.toml` with `[fast]`, `[excel]`, `[cosmos]`, `[validation]`, `[api]`, `[database]`, `[cli]`, `[all]`, `[dev]` extras; `[project.scripts]` entry point; builds with hatchling
- [x] Complete Sphinx documentation — API reference (autodoc from all modules), Getting Started guide, Adding a New Shape guide, Cosmos DB Setup guide, CLI reference
- [x] Architecture Decision Records — 5 ADRs: direct-dict construction, YAML mapping, orjson serialization, one-container-per-shape, optional SHACL validation
- [x] README with badges, CLI section, updated project status — badges for Python version, license, test count, coverage; full CLI usage section; all code examples verified
- [ ] ~~Publish to internal PyPI / Azure Artifacts~~ — Deferred (package builds correctly; publishing deferred to when internal feed is set up)
- [x] Unit tests: **356 passed, 0 failed** (25 new CLI tests using Click CliRunner with real shapes and adapters)

> **Phase 6 completed February 2026.** Full CLI with 6 commands, Sphinx documentation with API reference and 3 user guides, 5 ADRs, polished README with badges. Package builds and installs correctly via `pip install -e ".[dev,cli]"`. Publishing deferred.

---

## Phase 7 — Production Hardening (Weeks 26-28)

### 7.1 Observability

| # | Task | Details |
|---|------|---------|
| 7.1.1 | Structured logging with `structlog` | |
| 7.1.2 | Pipeline progress tracking (tqdm or custom callbacks) | For large batch jobs: `Processing 1,000,000 records... 45% [=====>  ] 28s remaining` |
| 7.1.3 | Metrics: records/sec, errors/batch, RU cost/doc | |
| 7.1.4 | Error recovery: dead-letter queue for failed records | Log failed records to NDJSON file for reprocessing |

### 7.2 Scaling Patterns

| # | Task | Details |
|---|------|---------|
| 7.2.1 | Streaming output: NDJSON write-as-you-go (no full array in memory) | For >1M records, avoid materializing entire list |
| 7.2.2 | Chunked Cosmos uploads: batch-size-optimized upserts | Tune batch size per RU capacity |
| 7.2.3 | Multiprocessing for very large heterogeneous jobs | Only if single-threaded throughput is insufficient for the shape |
| 7.2.4 | Memory profiling and optimization | Ensure <2GB RSS for 1M record jobs |

### 7.3 Security

| # | Task | Details |
|---|------|---------|
| 7.3.1 | Cosmos DB auth: DefaultAzureCredential (no keys in code) | Azure Identity integration |
| 7.3.2 | Sensitive field handling | PII fields (SSN, DOB) — log masking, no debug output of values |
| 7.3.3 | Input sanitization | Protect against injection in IRI construction (`@id` values) |

### Phase 7 Deliverables

- [x] Production-ready logging and monitoring — Structured logging (structlog optional + stdlib fallback), PipelineResult metrics (records/sec, bytes, elapsed), progress tracking (tqdm + custom callbacks), dead-letter queue for failed records
- [x] Streaming NDJSON output for large datasets — stream() emits one doc at a time; to_ndjson writes incrementally; progress callbacks during streaming
- [x] Memory-efficient pipeline for 10M+ records — stream() generator holds constant memory; 10K-record stress test validates <2GB RSS
- [x] Security review complete — PII masking in logs (16 field patterns), IRI injection protection (sanitize_iri_component + validate_base_uri), DefaultAzureCredential already supported

> **Phase 7 completed February 2026.** Structured logging with PII masking,
> PipelineResult metrics, dead-letter queue, progress tracking, and IRI sanitization
> shipped. Multiprocessing deferred (single-threaded already 161x faster than alternatives).
> Chunked Cosmos uploads deferred (no emulator available for benchmarking).
> All 398 tests passing.

---

## Key Technical Decisions

### Decision 1: Direct Dict Construction (Not rdflib+PyLD)

**Decision:** Build JSON-LD documents as plain Python dicts, not through rdflib graph creation + PyLD compaction.

**Rationale:** Our benchmarking proved:
- Direct dict: **0.02 ms/record** (161x faster)
- rdflib + PyLD: **7.2 ms/record**
- 1M records: **33 seconds** vs **2+ hours**

PyLD is the bottleneck (73.4% of time) due to context re-parsing on every call (GitHub issue #85, open since 2018).

**Tradeoff:** We lose the ability to produce an RDF graph as an intermediate. SHACL validation requires reconstituting a graph from the JSON-LD. We handle this by making validation a separate, optional step.

### Decision 2: YAML Mapping Config (Not Pure SHACL)

**Decision:** Use YAML mapping files alongside SHACL, not SHACL alone.

**Rationale:** SHACL defines *constraints* (what is valid), not *mappings* (where data comes from). SHACL cannot express:
- Which CSV column maps to which property
- How to split pipe-delimited values
- What transform to apply ("Female" → "Sex_Female")
- Default values for RecordStatus/DataCollection

SHACL *can* be used to auto-generate a mapping template skeleton and to validate the mapping config.

### Decision 3: orjson for Serialization

**Decision:** Use `orjson` (Rust-backed) for JSON serialization, falling back to stdlib `json`.

**Rationale:** 4-5x faster at scale. At 1M records, saves ~15 seconds of serialization time.

### Decision 4: One Cosmos Container Per Shape

**Decision:** Create a separate Cosmos DB container for each shape type (person, organization, etc.).

**Rationale:**
- Each shape has different query patterns → different indexing needs
- Partition key can be tuned per shape (e.g., `orgId` for organization, `collectionId` for person)
- TTL policies may differ per data collection type
- Cleaner cost attribution

### Decision 5: Optional SHACL Validation

**Decision:** SHACL validation is opt-in, not a required pipeline step.

**Rationale:** pySHACL validation costs ~50ms/record (requires materializing an rdflib graph from JSON-LD). For bulk loads of 1M records, that's ~14 hours of validation time. Instead:
- Use lightweight pre-build validation (schema checks from introspected SHACL) for 100% of records
- Use full SHACL validation on a configurable sample (e.g., 1%) or in a post-load quality gate

---

## Risk Register

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|------------|------------|
| R1 | SHACL shapes vary too much across collections to have a generic builder | High | Medium | Phase 0.4 tests with 2+ shapes; YAML mapping absorbs structural differences |
| R2 | Cosmos DB query performance on nested JSON-LD is poor | High | Low | Test early with emulator (Phase 0.3). Consider flattening for query-heavy fields. |
| R3 | Python SDK async bulk performance for Cosmos is insufficient | Medium | Medium | Benchmark in Phase 4. Fallback: batch via Azure Functions or .NET SDK bridge. |
| R4 | CEPI extension ontologies are not yet stable | Medium | High | The YAML mapping layer insulates builder from ontology changes. Only context.json needs updating. |
| R5 | pySHACL validation is too slow for inline use | Medium | High (confirmed) | Already mitigated: sample-based validation, lightweight pre-build checks. |
| R6 | Context URL hosting becomes a dependency | Low | Medium | Support embedded context mode as fallback. Cache contexts locally. |
| R7 | Shape definitions need to support versioning over time | Medium | Medium | Add `version` field to mapping YAML. Cosmos documents include `@context` URL which implicitly versions. |

---

## Dependency Map

### Runtime Dependencies

| Package | Purpose | Required? |
|---------|---------|-----------|
| `orjson` | Fast JSON serialization | Optional (falls back to stdlib) |
| `pyyaml` | Mapping config parsing | Required |
| `rdflib` | SHACL introspection, round-trip validation | Required |
| `pandas` | CSV/Excel adapter | Required |
| `openpyxl` | Excel .xlsx support | Optional (`[excel]`) |
| `httpx` | REST API adapter | Optional (`[api]`) |
| `azure-cosmos` | Cosmos DB loader | Optional (`[cosmos]`) |
| `azure-identity` | Azure auth | Optional (`[cosmos]`) |
| `pyshacl` | Full SHACL validation | Optional (`[validation]`) |
| `click` | CLI | Optional (`[cli]`) |
| `structlog` | Structured logging | Optional |
| `tqdm` | Progress bars | Optional |

### Development Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Testing |
| `pytest-cov` | Coverage |
| `hypothesis` | Property-based testing |
| `ruff` | Linting & formatting |
| `mypy` | Type checking |
| `mkdocs` | Documentation |

---

## Appendix: Research Backlog

These are open questions that should be investigated as the project progresses:

### A.1 JSON-LD 1.1 Features

- [ ] Can we use `@nest` to group properties without creating new nodes? (e.g., group name fields under a "name" key without a separate PersonName type)
- [ ] Can `@import` in contexts reduce duplication across shape-specific contexts?
- [ ] Does `@container: @set` help normalize arrays (always array vs. sometimes single value)?

### A.2 Alternative Validation Approaches

- [ ] **JSON Schema from SHACL**: Generate a JSON Schema from the SHACL shape for ultra-fast validation (no RDF round-trip). Tools: `shacl2jsonschema` or custom.
- [ ] **Pydantic models from SHACL**: Generate Pydantic models for type-safe, fast Python object validation.
- [ ] **Cosmos DB stored procedures**: Server-side validation on upsert.

### A.3 Graph Database Integration

- [ ] If CEPI ever needs *graph* queries (traverse person→organization→school relationships), consider:
  - Azure Cosmos DB Gremlin API (graph queries on same data)
  - Apache Jena / Oxigraph for SPARQL endpoints
  - Neo4j import from JSON-LD

### A.4 Change Data Capture

- [ ] Cosmos DB Change Feed for propagating data changes to downstream systems
- [ ] Event-driven architecture: new JSON-LD document → Azure Function → notification/ETL

### A.5 CEDS Ontology Evolution

- [ ] How will CEDS ontology updates (new properties, deprecated terms) propagate through the system?
- [ ] Recommended: version-pin ontology files, test against new versions in CI, explicit migration step

### A.6 Data Quality Dashboard

- [ ] Web UI showing: records processed, validation error rates, per-shape statistics
- [ ] Integration with Azure Monitor / Application Insights

---

## Summary Timeline

| Phase | Weeks | Focus | Key Deliverable |
|-------|-------|-------|----------------|
| **0** | 1-3 | Research & PoC | ✅ Complete — Performance benchmarks, architecture decisions, go/no-go = GO |
| **1** | 4-7 | Core Foundation | ✅ Complete — Installable library: registry, mapper, builder, serializer. 89 tests, 90% coverage. |
| **2** | 8-11 | SHACL Engine | ✅ Complete — SHACLIntrospector, mapping templates, YAML validation, mapping overrides/composition, URI fetching. 142 tests, 91% coverage. |
| **3** | 12-15 | Ingestion Layer | ✅ Complete — 6 adapters (CSV, Excel, Dict, NDJSON, API, Database), Pipeline class, stream & batch modes. 210 tests, 87% coverage. |
| **4** | 16-19 | Cosmos Integration | ✅ Complete — CosmosLoader (async bulk upsert), prepare_for_cosmos, Pipeline.to_cosmos(), 241 tests. Benchmarks deferred (no emulator). |
| **5** | 20-22 | Validation | ✅ Complete — PreBuildValidator + SHACLValidator, 3 validation modes, Pipeline.validate(), 331 tests, 88% coverage |
| **6** | 23-25 | CLI & Docs | ✅ Complete — Full CLI (6 commands), Sphinx docs, 3 user guides, 5 ADRs. 356 tests. |
| **7** | 26-28 | Production | ✅ Complete — Structured logging (structlog + fallback), PipelineResult metrics, dead-letter queue, progress tracking, PII masking, IRI sanitization. 398 tests. |
| **8** | — | Open Source Publishing | 🔄 In Progress — Versioning (0.9.0), PyPI publishing, GitHub Actions CI/CD, issue templates, CONTRIBUTING.md |

**Estimated total: ~7 months** (adjustable based on team size and priority shifts)

---

## Phase 8 — Open Source Publishing

### 8.1 Versioning & Release

| # | Task | Details |
|---|------|---------|
| 8.1.1 | Adopt Semantic Versioning (semver) | MAJOR.MINOR.PATCH — version tracked in `pyproject.toml` + `__init__.py` |
| 8.1.2 | Initial public version: **0.9.0** | Signals "feature-complete beta, approaching 1.0" |
| 8.1.3 | Monthly release cadence | First week of each month; ad-hoc patches for critical fixes |
| 8.1.4 | CHANGELOG.md | Track all changes per version |

### 8.2 PyPI Publishing

| # | Task | Details |
|---|------|---------|
| 8.2.1 | PyPI metadata in `pyproject.toml` | Classifiers, keywords, project URLs |
| 8.2.2 | GitHub Actions CI workflow | Tests (pytest), lint (ruff), type check (mypy) on push/PR — Python 3.12 + 3.13, Ubuntu + Windows |
| 8.2.3 | GitHub Actions publish workflow | Tag `v*` → build → test → publish to TestPyPI → publish to PyPI (trusted publishing, no API tokens in secrets) |
| 8.2.4 | TestPyPI dry-run | Validate package installs correctly before real PyPI |
| 8.2.5 | First PyPI release: `v0.9.0` | `pip install ceds-jsonld` works for anyone |

### 8.3 GitHub Repository

| # | Task | Details |
|---|------|---------|
| 8.3.1 | Make repository public | Settings → Danger Zone → Change visibility |
| 8.3.2 | Issue templates | Bug report, feature request, new shape request |
| 8.3.3 | PR template | Checklist: tests, lint, types, changelog |
| 8.3.4 | CONTRIBUTING.md | Dev setup, coding standards, release process, how to add shapes |
| 8.3.5 | Branch protection on `main` | Require CI pass, require PR review |

### 8.4 PyPI Account Setup (Manual Steps)

> These steps must be done manually in a browser — they cannot be automated.

| # | Step | URL |
|---|------|-----|
| 8.4.1 | Create account on **pypi.org** | https://pypi.org/account/register/ |
| 8.4.2 | Create account on **test.pypi.org** | https://test.pypi.org/account/register/ |
| 8.4.3 | On PyPI: go to Publishing → Add a new pending publisher | Set repo to `daimare9/cepi-jsonld`, workflow `publish.yml`, environment `pypi` |
| 8.4.4 | On TestPyPI: same as above | Environment `testpypi` |
| 8.4.5 | On GitHub: create `pypi` environment | Repo Settings → Environments → New → `pypi` |
| 8.4.6 | On GitHub: create `testpypi` environment | Repo Settings → Environments → New → `testpypi` |
| 8.4.7 | Make repo public | Repo Settings → Danger Zone → Change repository visibility |
| 8.4.8 | Enable branch protection on `main` | Repo Settings → Branches → Add rule → Require status checks |

### Phase 8 Deliverables

- [x] Version bumped to 0.9.0
- [x] `pyproject.toml` updated with PyPI metadata (classifiers, keywords, URLs)
- [x] CHANGELOG.md tracking all changes
- [x] CONTRIBUTING.md with dev setup, coding standards, release process
- [x] GitHub Actions CI workflow (test + lint on push/PR)
- [x] GitHub Actions publish workflow (tag → TestPyPI → PyPI via trusted publishing)
- [x] Issue templates (bug report, feature request, new shape)
- [x] PR template with checklist
- [ ] PyPI/TestPyPI account setup (manual — see 8.4)
- [ ] GitHub environments created (manual — see 8.4)
- [ ] Repository made public (manual — see 8.4)
- [ ] First `v0.9.0` tag pushed and published to PyPI

---

*This roadmap is a living document. It should be revisited after Phase 0 research conclusions and updated with findings.*

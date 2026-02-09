# CEDS JSON-LD Generator Library — Full Roadmap

**Project:** `ceds-jsonld` — A Python library for ingesting education data from any source, mapping it to CEDS/CEPI ontology-backed RDF shapes, outputting conformant JSON-LD, and loading it into Azure Cosmos DB.

**Date:** February 9, 2026
**Status:** v1.0 Complete — v1.1 (Native Adapters) Research Complete, v2.0 Phase 1 (Synthetic Data Generator) Research Validated with PoC, Phase 2 (AI-Assisted Mapping Wizard) Research Validated with PoC

---

## Table of Contents

1. [Vision & Goals](#1-vision--goals)
2. [Architecture Overview](#2-architecture-overview)
3. [Ontology & Shape Management Strategy](#3-ontology--shape-management-strategy)
4. [v1.0 Release History](#v10-release-history)
5. [v1.1 — Native Adapters](#v11--native-adapters)
6. [v2.0 — Phase 1: Synthetic Data Generator](#v20--phase-1-synthetic-data-generator)
7. [v2.0 — Phase 2: AI-Assisted Mapping Wizard + Quick-Wins](#v20--phase-2-ai-assisted-mapping-wizard--quick-wins)
8. [v2.0 — Future Features (Backlog)](#v20--future-features-backlog)
9. [Key Technical Decisions](#key-technical-decisions)
10. [Risk Register](#risk-register)
11. [Dependency Map](#dependency-map)
12. [Appendix: Research Backlog](#appendix-research-backlog)

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

## v1.0 Release History

> v1.0 development ran ~7 months across 9 phases. Detailed task tables, deliverable
> checklists, and per-issue bug fix notes are preserved in git history. Below is the
> compact summary.

| Phase | Focus | Key Deliverable |
|-------|-------|----------------|
| **0** | Research & PoC | Performance benchmarks, architecture decisions, go/no-go = GO |
| **1** | Core Foundation | Installable library: registry, mapper, builder, serializer. 89 tests, 90% coverage. |
| **2** | SHACL Engine | SHACLIntrospector, mapping templates, YAML validation, mapping overrides/composition, URI fetching. 142 tests, 91% coverage. |
| **3** | Ingestion Layer | 6 adapters (CSV, Excel, Dict, NDJSON, API, Database), Pipeline class, stream & batch modes. 210 tests, 87% coverage. |
| **4** | Cosmos Integration | CosmosLoader (async bulk upsert), prepare_for_cosmos, Pipeline.to_cosmos(). 241 tests. |
| **5** | Validation | PreBuildValidator + SHACLValidator, 3 validation modes, Pipeline.validate(). 331 tests, 88% coverage. |
| **6** | CLI & Docs | Full CLI (6 commands), Sphinx docs, 3 user guides, 5 ADRs. 356 tests. |
| **7** | Production Hardening | Structured logging, PipelineResult metrics, dead-letter queue, progress tracking, PII masking, IRI sanitization. 398 tests. |
| **8** | Open Source Publishing | Versioning (0.9.0+), PyPI publishing, GitHub Actions CI/CD, issue templates, CONTRIBUTING.md. |
| **—** | Pre-1.0 Stabilization | Bug fixes (#2–#30): transform hardening, validation improvements, adapter edge cases. **557 tests.** |

### Architectural Decisions Made in v1.0

1. **Direct dict construction** — 161x faster than rdflib + PyLD (0.02 ms/record vs. 7.2 ms)
2. **YAML mapping configs** — SHACL defines constraints; YAML defines source→target mappings
3. **orjson serialization** — 4-5x faster JSON output, stdlib fallback
4. **One Cosmos container per shape** — Tuned indexing/partitioning per query pattern
5. **Optional SHACL validation** — Lightweight pre-build for 100%; full pySHACL on sample

> **v1.0 completed February 2026.** All phases delivered, 557 tests passing, library
> published to PyPI as `ceds-jsonld` with extras: `[fast]`, `[excel]`, `[cosmos]`,
> `[validation]`, `[api]`, `[database]`, `[cli]`, `[observability]`, `[all]`.

---

## v1.1 — Native Adapters

**Status:** ✅ Research Complete (Jan 14, 2026)
**Research:** See `ResearchFiles/FEATURE7_NATIVE_ADAPTERS_RESEARCH.md` for full analysis.
**Target extras groups:** `[sheets]`, `[canvas]`, `[oneroster]`, `[snowflake]`, `[bigquery]`, `[databricks]`

### Overview

Extend the adapter layer with native connectors for the data sources education
organizations actually use: Google Sheets, Student Information Systems (Canvas,
PowerSchool, Infinite Campus, Blackbaud), and cloud data warehouses (Snowflake,
BigQuery, Databricks). All adapters follow the existing `SourceAdapter` ABC and
yield plain Python dicts — zero changes to downstream Pipeline/Builder/Serializer.

**Key research findings:**

- **Google Sheets** — `gspread` v6.2.1 returns `list[dict]` via `get_all_records()`,
  mapping directly to `SourceAdapter.read()`. Highest demand in K-12.
- **Cloud warehouses** — All three (Snowflake, BigQuery, Databricks) follow PEP 249
  DB-API 2.0 with dict-convertible rows (`DictCursor`, `dict(row)`, `Row.asDict()`).
  ~80-120 lines each.
- **Canvas LMS** — Best-documented SIS with official Python library (`canvasapi`).
  Paginated REST API with `PaginatedList` objects.
- **OneRoster standard** — Covers Infinite Campus, ClassLink, Clever, Aeries, and
  others. One adapter for many SIS platforms.
- **PowerSchool / Blackbaud** — Standard REST + OAuth2 APIs. No custom adapter needed
  — factory functions pre-configure `APIAdapter` with vendor-specific defaults.

### Task Table

| # | Task | Details | Effort Est. |
|---|------|---------|-------------|
| **Phase A — Spreadsheets & Cloud Warehouses** ||||
| 1.1 | `GoogleSheetsAdapter` | `gspread` v6+. Auth: service account, OAuth2, API key. `get_all_records()` → `Iterator[dict]`. | 1-2 days |
| 1.2 | `SnowflakeAdapter` | `snowflake-connector-python`. `DictCursor` for dict results, `fetchmany()` for batching. Auth: key-pair, OAuth, SSO, workload identity. | 1-2 days |
| 1.3 | `BigQueryAdapter` | `google-cloud-bigquery`. `dict(row)` iteration + `list_rows()` direct table access. Auth: ADC, service account. | 1-2 days |
| 1.4 | `DatabricksAdapter` | `databricks-sql-connector`. `Row.asDict()` + `fetchmany()` batch. Auth: PAT, OAuth M2M/U2M. | 1-2 days |
| 1.5 | Tests: Phase A adapters | Unit tests + integration tests for all 4 adapters. | 1-2 days |
| **Phase B — SIS Platforms** ||||
| 1.6 | `CanvasAdapter` | `canvasapi` v3+. Paginated `PaginatedList` → dict per record. Users, enrollments, courses. | 2-3 days |
| 1.7 | `OneRosterAdapter` | `httpx`. Standard OneRoster 1.1 endpoints (`/users`, `/orgs`, `/enrollments`). Covers Infinite Campus, ClassLink, Clever, Aeries. | 2-3 days |
| 1.8 | Tests: Phase B adapters | Unit tests + integration tests for Canvas + OneRoster. | 1-2 days |
| **Phase C — Templates & Documentation** ||||
| 1.9 | PowerSchool factory function | Pre-configured `APIAdapter` with PSQ-specific defaults + OAuth2 client credentials. 20-40 lines. | 0.5 day |
| 1.10 | Blackbaud factory function | Pre-configured `APIAdapter` with SKY API defaults + `Bb-Api-Subscription-Key` header. 30-50 lines. | 0.5 day |
| 1.11 | New extras in `pyproject.toml` | `[sheets]`, `[canvas]`, `[oneroster]`, `[snowflake]`, `[bigquery]`, `[databricks]`, `[sis]`, `[warehouse]`, `[all-adapters]` | 0.5 day |
| 1.12 | Documentation | Sphinx adapter guides with auth setup for each platform. README updates. | 2-3 days |

### Deliverables

- [ ] `GoogleSheetsAdapter` — read from any spreadsheet via title, key, or URL
- [ ] `SnowflakeAdapter` — SQL query → dict iteration via `DictCursor`
- [ ] `BigQueryAdapter` — SQL query or direct table read via `dict(row)`
- [ ] `DatabricksAdapter` — SQL query → dict iteration via `Row.asDict()`
- [ ] `CanvasAdapter` — paginated Canvas REST API via `canvasapi`
- [ ] `OneRosterAdapter` — standard OneRoster 1.1 endpoints (covers IC, ClassLink, Clever, Aeries)
- [ ] `powerschool_adapter()` factory function — pre-configured `APIAdapter`
- [ ] `blackbaud_adapter()` factory function — pre-configured `APIAdapter`
- [ ] New extras groups in `pyproject.toml` + convenience bundles (`[sis]`, `[warehouse]`, `[all-adapters]`)
- [ ] Tests for all new adapters (unit + integration)
- [ ] Sphinx docs with auth setup guides per platform

### End-User Experience

**Install (pick what you need):**
```bash
pip install ceds-jsonld[sheets]         # Google Sheets only
pip install ceds-jsonld[snowflake]      # Snowflake only
pip install ceds-jsonld[warehouse]      # All 3 cloud warehouses
pip install ceds-jsonld[sis]            # Canvas + OneRoster
pip install ceds-jsonld[all-adapters]   # Everything
```

**Google Sheets:**
```python
from ceds_jsonld import Pipeline
from ceds_jsonld.adapters import GoogleSheetsAdapter

adapter = GoogleSheetsAdapter(
    "Student Demographics 2026",
    service_account_file="key.json",
)
pipeline = Pipeline(adapter=adapter, shape="Person")
results = pipeline.run()
```

**Snowflake:**
```python
from ceds_jsonld.adapters import SnowflakeAdapter

adapter = SnowflakeAdapter(
    query="SELECT * FROM education.students WHERE district = %s",
    account="myorg-myaccount",
    private_key_file="/path/to/key.p8",
    warehouse="compute_wh",
    database="education_db",
    params=("District 42",),
)
pipeline = Pipeline(adapter=adapter, shape="Person")
```

**OneRoster (any compliant SIS):**
```python
from ceds_jsonld.adapters import OneRosterAdapter

adapter = OneRosterAdapter(
    base_url="https://sis.district.edu/ims/oneroster/v1p1",
    endpoint="users",
    client_id="...",
    client_secret="...",
    filter="role='student'",
)
pipeline = Pipeline(adapter=adapter, shape="Person")
```

---

<!-- BEGIN v2.0 -->

## v2.0 — Phase 1: Synthetic Data Generator

**Status:** ✅ Research Validated with End-to-End Proof of Concept (Feb 9, 2026)
**Research:** See `ResearchFiles/FEATURE4_SYNTHETIC_DATA_RESEARCH.md` for full analysis.
**PoC Script:** `ResearchFiles/phase1_benchmarks/bench_person_jsonld_dynamic.py` (914 lines)
**PoC Output:** `ResearchFiles/phase1_benchmarks/results/person_jsonld_dynamic_20260209_092102.json`
**Target extras group:** `pip install ceds-jsonld[sdg]`

> **PoC Validation Summary (Feb 9, 2026):**
> A fully dynamic end-to-end test generated a complete Person JSON-LD document with
> zero hard-coded values. Key findings:
> - **Three ontology sources required:** CEDS-Ontology.rdf (235,570 triples) + Common.ttl
>   (+60) + Person_Extension_Ontology.ttl (+42) must all load into a single rdflib Graph.
> - **Two concept scheme resolution strategies:** (A) `sh:in` direct resolve for properties
>   with explicit enumeration; (B) `schema:rangeIncludes` → class → NamedIndividual
>   members for properties without `sh:in` (e.g., hasSex, hasRaceAndEthnicity).
> - **SHACL property corrections:** hasSex was P000011 (wrong — that's AYP Status),
>   corrected to P000255. hasRaceAndEthnicity was P000282 (wrong — that's Title I),
>   corrected to P001943.
> - **Performance (RTX 3090, Qwen3 4B full weights via transformers):** 9s ontology load,
>   7.3s model load, 6.1s LLM generation (83 tokens at 14 tok/s), 0.088ms dict construction.
>   Ollama with GGUF quantization expected ~5x faster for generation (~80 tok/s).
> - **Property classification:** 7 literal (LLM), 3 concept scheme (random select),
>   10 structural (RecordStatus/DataCollection defaults from mapping YAML).
> - **All 557 project tests pass** after SHACL + context fixes.

### Overview

Generate fully valid, realistic CEDS-conformant synthetic data for any registered shape.
Two-tier approach:

1. **Concept Scheme properties** (enumerated values like Sex, Race, GradeLevel) — extract
   valid `NamedIndividual` IRIs directly from the ontology RDF. Random selection, zero LLM cost.
2. **Literal value properties** (names, dates, IDs) — local LLM generates contextually
   appropriate values using ontology metadata (rdfs:label, dc:description, constraints).

**Runtime:** `transformers` + `torch` (in-process, pre-built wheels for all platforms
including Windows+CUDA, no C compiler required). `llama-cpp-python` was rejected because
it requires C/C++ build tools on Windows. Ollama auto-detected as power-user alternative.
Three-tier fallback: LLM → cache → deterministic generators.

**Model:** Qwen3 4B default (~8 GB full weights, BFloat16 on GPU, auto-downloaded via
`huggingface-hub` on first use). Qwen3 0.6B available as lighter CPU option.

### Task Table

| # | Task | Details |
|---|------|---------|
| 1.1 | `ConceptSchemeResolver` class | Parse ontology RDF, resolve concept scheme values via both strategies: (A) `sh:in` IRIs → notation/label, and (B) `schema:rangeIncludes` → class → NamedIndividual members. Must load all 3 ontology sources. |
| 1.2 | `FallbackGenerators` module | Pure-Python generators for all XSD types + name-aware string defaults |
| 1.3 | `MappingAwareAssembler` class | Read mapping YAML, assemble CSV rows, handle pipe-delimited multi-value fields |
| 1.4 | `SyntheticDataGenerator` class | Core orchestrator: concept scheme + fallback generation |
| 1.5 | CSV + NDJSON output writers | Write to file or stdout |
| 1.6 | Round-trip integration tests | Generate CSV → Pipeline → JSON-LD → SHACL validate → pass |
| 1.7 | Add `[sdg]` extras to `pyproject.toml` | `torch>=2.2`, `transformers>=4.40`, `huggingface-hub>=0.20` |
| 1.8 | `OntologyMetadataExtractor` class | Extract rdfs:label, dc:description, maxLength, rangeIncludes from ontology for prompt context |
| 1.9 | `LLMValueGenerator` class | Build prompts from metadata, call transformers with structured output parsing, parse responses |
| 1.10 | Ollama auto-detection | If Ollama is running on localhost:11434, prefer it over in-process transformers for faster GGUF generation |
| 1.11 | File-based caching layer | `~/.ceds_jsonld/cache/` with model-keyed entries; cache LLM-generated values for reuse |
| 1.12 | Three-tier fallback logic | LLM (in-process or Ollama) → cache → deterministic fallback generators |
| 1.13 | Post-generation validation | Verify LLM values match datatype constraints (maxLength, date format, numeric ranges) |
| 1.14 | `generate-sample` CLI command | Options: `--shape`, `--count`, `--format`, `--model`, `--seed`, `--no-llm`, `--cache-dir` |
| 1.15 | `generate-cache` CLI command | Pre-warm cache for CI environments (no LLM needed at CI time) |
| 1.16 | Ship default Person cache | Commit pre-generated cache files for zero-setup CI |
| 1.17 | Streaming mode | Iterator/generator pattern for 100K+ row generation |
| 1.18 | JSON-LD output mode | Generate → Pipeline → JSON-LD documents (end-to-end) |
| 1.19 | Benchmark suite | Time: LLM generation, cached generation, 10K/100K/1M row assembly |
| 1.20 | Model comparison tests | Test Qwen3 4B vs. Granite4 3B vs. Phi-4 Mini for value quality |
| 1.21 | Distribution profiles | Optional YAML config for demographic distributions |
| 1.22 | Documentation | Sphinx docs, README examples, getting-started guide |

### Deliverables

- [ ] `ConceptSchemeResolver` + `FallbackGenerators` — zero-LLM synthetic data for any shape
- [ ] `LLMValueGenerator` + `OntologyMetadataExtractor` — LLM-powered realistic literals
- [ ] Caching layer — generate once, reuse everywhere (including CI)
- [ ] CLI commands: `generate-sample`, `generate-cache`
- [ ] `[sdg]` extras group in `pyproject.toml` (`torch`, `transformers`, `huggingface-hub`)
- [ ] Round-trip tests: generated data passes full Pipeline + SHACL validation
- [ ] Benchmark: LLM vs. cached vs. fallback generation speed
- [ ] Docs: user guide, API reference, README section

### End-User Experience

**Install:**
```bash
pip install ceds-jsonld[sdg]
```

**Python API:**
```python
from ceds_jsonld import Pipeline, SyntheticDataGenerator

gen = SyntheticDataGenerator("Person")
df = gen.generate(count=500)  # pandas DataFrame, ready for Pipeline
```

**CLI:**
```bash
ceds-jsonld generate-sample --shape Person --count 1000 --format csv -o sample.csv
ceds-jsonld generate-sample --shape Person --count 50 --format jsonld -o sample.jsonld
```

Under the hood: first run auto-downloads model (~8 GB), subsequent runs use cache.
No C compiler, no background service, no `ollama pull`, no config files.

---

## v2.0 — Phase 2: AI-Assisted Mapping Wizard + Quick-Wins

**Status:** ✅ Research Validated with End-to-End Proof of Concept (Feb 9, 2026)
**Research:** See `ResearchFiles/FEATURE1_AI_MAPPING_WIZARD_RESEARCH.md` for full analysis.

> **PoC Validation Summary (Feb 9, 2026):**
> A fully working PoC tested three-phase column-to-SHACL matching against 3 progressively
> harder test CSVs (34 total columns with abbreviated, verbose, and short-code naming). Key findings:
> - **Three-phase matching pipeline:** (1) Concept-value matching resolves ~38% of columns
>   in <1ms by comparing source values against CEDS concept scheme enums (3 strategies:
>   direct, CEDS-prefixed, abbreviation-prefix). (2) Heuristic name matching resolves ~3%
>   via normalized fuzzy substring + datatype compatibility. (3) LLM resolves remaining ~59%.
> - **100% mapping accuracy** across all 34 columns in 3 test CSVs — no incorrect mappings.
> - **Concept-value matching is the breakout finding:** Columns like `GENDER`, `RACE_ETH`,
>   `IDSystem`, `IDType` are resolved purely by value overlap against known concept scheme
>   enums — no column name analysis, no LLM, deterministic, <1ms.
> - **LLM configuration:** Qwen3 4B via `transformers` (BFloat16, SDPA, RTX 3090). Thinking
>   mode disabled (`/no_think`) — saves 50% tokens with no accuracy loss. 13.6–14.0 tok/s.
> - **Correct transform suggestions:** `date_format`, `sex_prefix`, `race_prefix`, `int_clean`
>   accurately suggested based on column data patterns.
> - **Architecture upgraded:** Original two-phase design (heuristic → LLM) upgraded to
>   three-phase (concept-value → heuristic → LLM) based on PoC findings.

### Overview

AI-assisted wizard that reads a user's CSV/Excel column headers and sample values,
then suggests a complete `_mapping.yaml` config mapping source columns to CEDS shape
properties — including transform recommendations and confidence scores.

Three-phase matching approach (validated by PoC):
1. **Concept-value matching** — Compare column distinct values against CEDS concept scheme
   named individual enums. Three strategies: direct, CEDS-prefixed, abbreviation-prefix.
   Resolves ~38% of columns in <1ms with 1.00 confidence. Zero LLM calls.
2. **Heuristic name matching** — Exact/fuzzy name matching, datatype compatibility.
   Handles additional columns with zero LLM calls.
3. **LLM-assisted resolution** — For remaining columns, the same `transformers` + `torch`
   engine from Phase 1 reads column names + sample values + ontology metadata and suggests
   mappings with confidence scores. Local-only (FERPA compliant).

Also includes three quick-win features that complement the wizard.

### Task Table

| # | Task | Details |
|---|------|---------||
| 2.1 | `ColumnProfiler` class | Analyze CSV/Excel columns: sample values, type inference, null rates, delimiters |
| 2.2 | `ShapeMetadataCollector` class | Aggregate target properties from introspector + ontology + transforms |
| 2.3 | `HeuristicMatcher` class | Scoring engine: name matching, fuzzy match, datatype compat, concept overlap |
| 2.4 | `MatchingEngine` orchestrator | Two-phase: heuristic first, LLM for unresolved columns |
| 2.5 | `MappingAssembler` class | Build complete YAML config + confidence annotations from matches |
| 2.6 | `WizardResult` dataclass | Config + confidence report + unmapped lists + YAML text |
| 2.7 | Tests: heuristic matching | Test name matching, type inference, concept scheme overlap |
| 2.8 | Tests: end-to-end | CSV → wizard → YAML → Pipeline → valid JSON-LD |
| 2.9 | LLM prompt builder | Construct mapping prompt from unresolved columns + shape properties |
| 2.10 | LLM response validator | Verify: properties exist, transforms exist, no hallucinations |
| 2.11 | Integration with Phase 1 LLM engine | Reuse Llama/Ollama loading, model cache, three-tier fallback |
| 2.12 | Transform suggestion logic | Pattern-based + LLM-assisted transform recommendations |
| 2.13 | Tests: LLM matching | Mocked LLM responses (live LLM test with `[sdg]` flag) |
| 2.14 | `map-wizard` CLI command | Options: input, shape, output, no-llm, preview, threshold, mask-pii |
| 2.15 | Preview mode | Run N records through Pipeline, show JSON-LD output |
| 2.16 | Shape auto-detection | Column overlap scoring across registered shapes |
| 2.17 | YAML annotation output | Write confidence comments, review markers, unmapped notes |
| 2.18 | QW-1: `--validate-only` HTML report | Beautiful pass/fail per record, SHACL violations highlighted |
| 2.19 | QW-2: `introspect` Markdown table output | Every shape + required properties in copy-paste-ready table |
| 2.20 | QW-3: Built-in `benchmark` command | Compare pipeline run vs. baseline, auto-generate speedup report |
| 2.21 | Documentation | Sphinx docs, README section, "Your First Mapping" guide |

### Deliverables

- [ ] `MappingWizard` — heuristic + LLM-assisted column→property matching
- [ ] `ColumnProfiler` — CSV/Excel column analysis with type inference
- [ ] `HeuristicMatcher` — deterministic scoring (name, datatype, concept scheme overlap)
- [ ] LLM integration — reuses Phase 1 `transformers` + `torch` engine, zero new deps
- [ ] `map-wizard` CLI command with annotated YAML output + confidence scores
- [ ] Preview mode — sample records through Pipeline to validate mapping
- [ ] QW-1: `--validate-only` with HTML report
- [ ] QW-2: `introspect` Markdown table output
- [ ] QW-3: Built-in `benchmark` command
- [ ] Tests: heuristic matching, end-to-end, LLM matching
- [ ] Docs: user guide, API reference, README section

### End-User Experience

**CLI:**
```bash
ceds-jsonld map-wizard --input district_export.csv --shape person
ceds-jsonld map-wizard --input data.xlsx --shape person --output my_mapping.yaml --preview 3
ceds-jsonld map-wizard --input data.csv --shape person --no-llm  # heuristic-only
```

**Python API:**
```python
from ceds_jsonld import MappingWizard

wizard = MappingWizard()
result = wizard.suggest("district_export.csv", shape="person")
result.save("person_mapping.yaml")
```

No new dependencies required — LLM support comes from the `[sdg]` extras (Phase 1).
Heuristic-only mode works with the base install.

---

## v2.0 — Future Features (Backlog)

**Status:** 💡 Brainstorming / Feasibility Research

These are **candidate features** for v2.1+ and beyond. Nothing here is committed —
each item needs dedicated research, feasibility analysis, and prioritization before
being promoted to a real phase.

---

### ~~Feature 1: AI-Assisted Mapping Wizard~~ → Promoted to v2.0 Phase 2

> Promoted to Phase 2. See [v2.0 — Phase 2](#v20--phase-2-ai-assisted-mapping-wizard--quick-wins) above.

---

### Feature 2: Visual Mapping Dashboard (Web UI)

- Drag-and-drop column → shape property with live JSON-LD preview.
- "Save mapping profile" → reusable YAML that the library can load.

**Research needed:**
- [ ] Framework choice (Streamlit, Gradio, FastAPI + React, Panel)
- [ ] Hosting model (local-only, optional cloud, embeddable)
- [ ] Integration with existing YAML mapping config format
- [ ] Scope boundary — keep the library headless, ship UI as a separate package?

---

### Feature 3: Verifiable Credentials (VC) Generator

- Turn a Person + Enrollment + Course record into a W3C Verifiable Credential.
- Built-in support for Open Badges 3.0 / CLR 2.0.

**Research needed:**
- [ ] W3C VC Data Model 2.0 compatibility
- [ ] DID method support (did:web, did:key, did:ion)
- [ ] Open Badges 3.0 / CLR 2.0 spec alignment with CEDS shapes
- [ ] Signing libraries (PyJWT, didkit) + key management

---

### Feature 5: Multi-format Round-trip (JSON-LD ↔ RDF ↔ CSV/Parquet)

- `to_turtle()`, `to_rdf_graph()`, `from_rdf()` — one-liner triplestore/SPARQL integration.

**Research needed:**
- [ ] rdflib round-trip fidelity (context compaction loss?)
- [ ] Parquet schema generation from SHACL shapes
- [ ] SPARQL query patterns for CEDS data
- [ ] Triplestore compatibility (GraphDB, Stardog, Oxigraph, Fuseki)

---

### Feature 6: CEDS Version Migration Tool

- Auto-detect source CEDS version → target version. Apply predefined migration rules.

**Research needed:**
- [ ] CEDS versioning scheme and changelog analysis
- [ ] Breaking vs. non-breaking changes between CEDS releases
- [ ] Migration rule format (declarative YAML? Python transforms?)

---

### ~~Feature 7: Native Adapters People Actually Use~~ → Promoted to v1.1

> Promoted to v1.1. See [v1.1 — Native Adapters](#v11--native-adapters) above.

---

### Feature 8: Observability That Actually Matters

- OpenTelemetry traces + metrics, Grafana dashboard, PII leakage alerts.

**Research needed:**
- [ ] OpenTelemetry Python SDK integration patterns
- [ ] Span design: per-record vs. per-batch vs. per-pipeline-stage
- [ ] Compatibility with Azure Monitor / Application Insights exporters

---

### Feature 9: Community Shape Marketplace / Contrib System

- `ceds-jsonld list-shapes --remote` — pull community shapes from a central repo.

**Research needed:**
- [ ] Shape packaging format and versioning
- [ ] Central registry (GitHub org? PyPI sub-packages? OCI artifacts?)
- [ ] Governance model for community shapes

---

### Feature 10: PyPI + Conda + Docker + One-click Deploy

- Docker image with all extras, Helm chart / Azure Container App template.

**Research needed:**
- [ ] Docker image size optimization (slim base, multi-stage build)
- [ ] Conda-forge recipe and submission process
- [ ] ARM/Bicep template for full infra (Cosmos + Container App + Key Vault)

---

### Quick-Wins

| # | Feature | Notes |
|---|---------|-------|
| QW-1 | `--validate-only` mode with HTML report | Beautiful pass/fail per record, SHACL violations highlighted |
| QW-2 | `introspect` → Markdown table output | Every shape + required properties in copy-paste-ready table |
| QW-3 | Built-in `benchmark` command | Compare pipeline run vs. baseline, auto-generate speedup report |

---

### v2.0+ Prioritization

> With Synthetic Data Generator committed as Phase 1 and AI-Assisted Mapping Wizard +
> Quick-Wins committed as Phase 2, remaining features will be prioritized after Phase 2
> ships. Scoring criteria: **impact** (user value) vs. **effort** (dev weeks), with
> dependencies between features considered.

---

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
| R8 | Local LLM model too large for user's hardware | Medium | Medium | Default model is ~2.5 GB; fallback generators produce valid data without LLM. `--no-llm` flag bypasses entirely. |
| R9 | PyPI package size limit (100 MB) prevents bundling model | Low | High (confirmed) | Model auto-downloaded via `huggingface-hub` on first use. Pre-generated cache ships for CI. |
| R10 | LLM-generated values fail SHACL validation | Medium | Medium | Post-generation validation checks constraints. Invalid values fall back to deterministic generators. |
| R11 | SIS vendor APIs behind login walls; evolving endpoints | Medium | Medium | Build to standards (OneRoster) rather than vendor-specific APIs; REST-based vendors use factory functions on existing `APIAdapter`. |
| R12 | Cloud warehouse connectors bring heavy transitive deps (pyarrow) | Low | Medium | Each adapter in its own extras group; document minimum install. |

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
| `gspread` | Google Sheets adapter | Optional (`[sheets]`) |
| `canvasapi` | Canvas LMS adapter | Optional (`[canvas]`) |
| `snowflake-connector-python` | Snowflake adapter | Optional (`[snowflake]`) |
| `google-cloud-bigquery` | BigQuery adapter | Optional (`[bigquery]`) |
| `databricks-sql-connector` | Databricks adapter | Optional (`[databricks]`) |
| `azure-cosmos` | Cosmos DB loader | Optional (`[cosmos]`) |
| `azure-identity` | Azure auth | Optional (`[cosmos]`) |
| `pyshacl` | Full SHACL validation | Optional (`[validation]`) |
| `click` | CLI | Optional (`[cli]`) |
| `structlog` | Structured logging | Optional |
| `tqdm` | Progress bars | Optional |
| `torch` | Local LLM inference (synthetic data, mapping wizard) | Optional (`[sdg]`) |
| `transformers` | Model loading + generation | Optional (`[sdg]`) |
| `huggingface-hub` | Model auto-download | Optional (`[sdg]`) |

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

| Phase | Status | Key Deliverable |
|-------|--------|----------------|
| **v1.0 (Phases 0–8)** | ✅ Complete | Full library: registry, mapper, builder, serializer, 6 adapters, Cosmos loader, validation, CLI, docs, CI/CD. 557 tests. |
| **v1.1** | ✅ Research Complete | Native Adapters — 6 new adapter classes (Google Sheets, Snowflake, BigQuery, Databricks, Canvas, OneRoster) + 2 factory functions (PowerSchool, Blackbaud). 8 new extras groups. Est. 10-15 dev days. |
| **v2.0 Phase 1** | 📋 Planning | Synthetic Data Generator — concept scheme extraction + local LLM, `[sdg]` extras, CLI commands. |
| **v2.0 Phase 2** | ✅ Research Validated | AI-Assisted Mapping Wizard + Quick-Wins — three-phase matching (concept-value → heuristic → LLM), 100% accuracy on 34 test columns across 3 CSVs. Concept-value matching resolves ~38% with zero AI. |

---

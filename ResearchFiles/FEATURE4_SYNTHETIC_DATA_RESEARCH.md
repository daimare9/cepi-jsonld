# Feature 4: Synthetic Data Generator — Deep Dive Research

**Date:** February 9, 2026
**Branch:** `dev`
**Status:** Research Complete — Validated with End-to-End Proof of Concept

> **Update (Feb 9, 2026):** The original research (Feb 8) has been revised to reflect
> findings from a real end-to-end proof of concept (`bench_person_jsonld_dynamic.py`)
> that generated a complete Person JSON-LD document with **everything derived dynamically
> from the ontology**. Key corrections include namespace resolution, SHACL property
> number fixes, concept scheme resolution strategy, and real performance numbers from
> Qwen3 4B running on an RTX 3090.

---

## 1. Executive Summary

Build a **hybrid synthetic data generator** that uses two distinct strategies based
on the property type in the CEDS ontology:

1. **Concept Scheme properties (object properties with `sh:in`)** — Deterministic
   random selection from the full set of `owl:NamedIndividual` members of the concept
   scheme. No AI needed. The ontology already contains ~19,500 NamedIndividuals across
   hundreds of concept schemes. We just randomly select from the enum.

2. **Literal value properties (strings, dates, tokens, etc.)** — Use a **lightweight
   local LLM** running in-process via `llama-cpp-python` to generate contextually-appropriate
   values. The LLM receives the ontology metadata for each property (label, description,
   definition, datatype, maxLength, textFormat) and returns structured JSON arrays of
   realistic values. The model auto-downloads on first use — no external services needed.

**Why this is better than the Faker approach:**
- Faker requires hand-coded per-property generators that break when new shapes are added.
- An LLM reading `rdfs:label: "First Name"` + `dc:description: "The full legal first name
  given to a person at birth..."` + `maxLength: 75` can generate realistic first names
  **without any property-specific code**.
- The generator becomes **truly generic** — add any new CEDS shape and it generates
  valid data automatically, because the LLM reads the ontology metadata.

---

## 1.1 Critical Findings from Proof of Concept (Feb 9, 2026)

A fully dynamic end-to-end test was run using Qwen3 4B on an NVIDIA RTX 3090. The
script generated a complete, valid Person JSON-LD document with **zero hard-coded values**.
Below are the key findings that correct or refine the original research.

### 1.1.1 Ontology Namespace Resolution — Three Sources Required

The Person SHACL references IRIs from **three** ontology sources that must all be
loaded into a single rdflib Graph:

| Source | Format | Triples | Content |
|--------|--------|---------|---------|
| `CEDS-Ontology.rdf` | RDF/XML | 235,570 | Main CEDS ontology — properties, classes, NamedIndividuals |
| `Common.ttl` | Turtle | +60 | CEPI common extensions — DataCollection dates, RecordStatus fields |
| `Person_Extension_Ontology.ttl` | Turtle | +42 | CEPI person extensions — EducatorID NamedIndividual, HighestLevelOfEducationCompletedDetail |

**Why all three:** The SHACL `sh:in` list for `hasPersonIdentificationSystem` includes
`cepi:NI001571100001` (EducatorID) which lives in `Person_Extension_Ontology.ttl`, not
in the main CEDS ontology. If only CEDS-Ontology.rdf is loaded, this IRI resolves to
nothing and the concept scheme pool is missing a value.

**Implementation requirement:** The `ConceptSchemeResolver` must load all ontology files
for a shape — the base CEDS ontology plus any `Common.ttl` and shape-specific extension
ontologies. The file organization pattern (§3.1 of this document) already provides
for extension files per shape.

### 1.1.2 SHACL Property Number Corrections

Two property numbers in the Person SHACL were discovered to be incorrect:

| Property | SHACL (before fix) | Ontology reality | Correct property | Concept scheme |
|----------|-------------------|------------------|-----------------|----------------|
| `hasSex` | `ceds:P000011` | P000011 = **AYP Status** (NA/No/Yes/YesGrowth) | `ceds:P000255` | C000255: Female, Male, NotSelected |
| `hasRaceAndEthnicity` | `ceds:P000282` | P000282 = **Title I Instructional Services** (CareerAndTechnical/Math/...) | `ceds:P001943` | C001943: 8 race/ethnicity values |
| `hasPersonIdentificationSystem` | `ceds:P001571` | P001571 = **Person Identification System** ✅ | Correct | C001571: 21 values (20 CEDS + 1 CEPI EducatorID) |

**Root cause:** CEDS property numbers (P-numbers) are NOT concept scheme class numbers
(C-numbers) with a changed prefix. P000011 ≠ "Sex with class C000011". The actual
Sex property is P000255 (notation: `hasSex`, range: C000255).

**Resolution strategy for concept schemes where SHACL has no `sh:in`:**
1. Get the parent sub-shape's `sh:targetClass` (e.g., `C200011` for PersonSexGender)
2. Query the ontology for properties with `schema:domainIncludes = C200011`
3. Find the property whose `skos:notation` matches the context name
4. Follow its `schema:rangeIncludes` to a concept scheme class
5. Enumerate all `owl:NamedIndividual` members of that class

The SHACL and context JSON have been corrected. All 557 tests pass with the fix.

### 1.1.3 Concept Scheme Resolution — Two Paths

Not all concept scheme properties have `sh:in` lists in the SHACL. Two resolution
strategies are needed:

**Path A — `sh:in` present (explicit enumeration):**
```
SHACL property has sh:in → list of IRI references
→ resolve each IRI to skos:notation from ontology
→ done (e.g., hasPersonIdentificationSystem: 21 values)
```

**Path B — No `sh:in`, range is a concept scheme class:**
```
SHACL property path IRI → ontology lookup
→ schema:rangeIncludes → concept scheme class IRI
→ find all owl:NamedIndividual of that class → skos:notation
→ done (e.g., hasSex: 3 values from C000255, hasRaceAndEthnicity: 8 values from C001943)
```

**Implementation:** The `extract_property_metadata()` function handles both paths:
```python
if allowed_values_iris:  # Path A: sh:in present
    resolved_values = resolve_named_individuals(ontology, allowed_values_iris)
elif is_concept:  # Path B: rangeIncludes → class → NamedIndividuals
    resolved_values = resolve_concept_scheme_members(ontology, range_str)
```

### 1.1.4 Property Classification Algorithm

The proof of concept established this algorithm for classifying every property in
a SHACL shape tree:

```
For each root property in the shape tree:
  If the property has a node_shape → it references a sub-shape
    For each child property in the sub-shape:
      If child has node_class in {C200411, C200410} → STRUCTURAL (RecordStatus/DataCollection, use defaults)
      Else if child has allowed_values OR range is a non-XSD class → CONCEPT SCHEME (random select)
      Else → LITERAL (LLM generates)
```

For the Person shape, this classifies 17 properties:
- **7 literal** properties → LLM generates values
- **3 concept scheme** properties → random selection from ontology
- **10 structural** properties → use mapping YAML defaults (RecordStatus ×5, DataCollection ×5)

### 1.1.5 Actual Performance Numbers (RTX 3090, Qwen3 4B via transformers+torch)

| Phase | Time | Notes |
|-------|------|-------|
| Ontology load (SHACL + context + mapping + 3 RDF sources) | **9.0s** | 235,672 triples total; one-time cost, cacheable |
| Model load (Qwen3-4B, BFloat16, SDPA via transformers) | **7.3s** | 7,672 MB VRAM; from local HuggingFace cache |
| LLM generation (1 person, 7 literal fields) | **6.1s** | 83 tokens generated at 14 tok/s; single call |
| Direct dict construction | **0.088ms** | Builds complete Person JSON-LD from value pools |
| Structural validation | **< 1ms** | Checks @type, @context, @id, sub-shapes, typed literals |
| **Total wall time** | **23.3s** | Dominated by one-time loads; subsequent records ~0.1ms each |
| Peak VRAM | **7,890 MB** | Well within RTX 3090's 24 GB |

**Runtime stack used in PoC:** `torch==2.6.0+cu124`, `transformers==5.1.0`,
`huggingface-hub==1.4.1`, Python 3.12.4, CUDA 12.4, NVIDIA driver 560+.

**Key insight from performance numbers:** For bulk generation (100+ records), the
ontology and model loads are amortized. The actual per-record cost is the dict
construction time: **0.088ms** (same as the 161x-faster direct-dict benchmark from v1.0).
The LLM call is also amortized in the "generate-then-sample" strategy — one call per
property type generates a pool of values, then `random.choice()` for each record.

### 1.1.6 llama-cpp-python Rejected — Requires C Build Tools on Windows

The original research (\u00a75 of this document) recommended `llama-cpp-python` as the
primary LLM runtime. During PoC setup, we discovered that `llama-cpp-python` requires
C/C++ build tools (Visual Studio Build Tools or MinGW) to compile on Windows. Pre-built
wheels on PyPI are not consistently available for all Python + CUDA version combinations.

**Impact:** Our target users are state education agency data engineers. Requiring a 6+ GB
Visual Studio Build Tools download to run `pip install` is hostile to the end-user
experience and violates our design principle (Rule 9: "Design for the End User").

**Resolution:** Pivoted to `transformers` + `torch` as the primary runtime. PyTorch ships
pre-built wheels for Windows x64 (CUDA 11.8, 12.4), Linux x64, and macOS (arm64/x64).
`pip install torch transformers huggingface-hub` Just Works on all platforms.

**Trade-offs:**
| Aspect | llama-cpp-python (rejected) | transformers+torch (chosen) |
|--------|----------------------------|----------------------------|
| Install on Windows | Requires C build tools | Pre-built wheels ✅ |
| Pip size | ~25 MB | ~2.7 GB (CUDA) or ~200 MB (CPU-only) |
| Model format | GGUF quantized (~2.6 GB) | Full weights (~8 GB) |
| VRAM usage (4B model) | ~3 GB (Q4) | ~7.7 GB (BFloat16) |
| Generation speed | ~80 tok/s (Q4 GGUF est.) | ~14 tok/s (BF16 full, measured) |
| JSON enforcement | GBNF grammar (guaranteed) | Prompt engineering + parse + retry |

The larger download and slower generation speed are acceptable trade-offs because:
- The `[sdg]` extra is optional — most users never install it
- Generation happens once per property, then values are cached
- For users with Ollama installed, auto-detection provides the GGUF speed advantage
- A working `pip install` is non-negotiable for our user base

### 1.1.7 Generated Output Quality

The LLM produced realistic values without any property-specific code:

| Field | Generated Value | Quality Assessment |
|-------|----------------|-------------------|
| FirstName | "Emma" | Realistic US name ✅ |
| MiddleName | "Lila" | Realistic ✅ |
| LastOrSurname | "Johnson" | Realistic US surname ✅ |
| GenerationCodeOrSuffix | "II" | Valid suffix ✅ |
| Birthdate | "2010-05-15" | Valid YYYY-MM-DD, reasonable K-12 age ✅ |
| PersonIdentifier | "1234567890" | Valid token, 10 digits ✅ |
| hasPersonIdentifierType | "Student ID" | Reasonable ✅ |

The concept scheme values resolved correctly:
- `hasSex` → "Sex_Female" (from C000255: Female/Male/NotSelected)
- `hasRaceAndEthnicity` → "RaceAndEthnicity_HispanicOrLatinoEthnicity" (from C001943: 8 values)
- `hasPersonIdentificationSystem` → "PIN" (from C001571: 21 values)

The complete JSON-LD document matched the canonical `person_example.json` structure:
all top-level keys matched, all sub-shape `@type` values matched, all RecordStatus
and DataCollection sub-shapes present.

---

## 2. The Two Property Categories in CEDS

Auditing the CEDS ontology (258,596 lines, 2,301 properties, 19,489 NamedIndividuals)
reveals a clean split:

### 2.1 Concept Scheme Properties (Enumerated — Easy)

These are object properties whose range is a CEDS class (concept scheme). The valid
values are the `owl:NamedIndividual` members of that class. In SHACL, they appear as
`sh:in` lists.

**Example — `hasPersonIdentificationSystem` (P001571):**

```turtle
ceds:hasPersonIdentificationSystemShape a sh:PropertyShape ;
    sh:in ( ceds:NI001571173132 ceds:NI001571173129 ... cepi:NI001571100001 ) ;
    sh:path ceds:P001571 .
```

Each NamedIndividual in the ontology has rich metadata:
```xml
<owl:NamedIndividual rdf:about="http://ceds.ed.gov/terms#NI001571173116">
    <rdf:type rdf:resource="http://ceds.ed.gov/terms#C001571" />
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept" />
    <rdfs:label>Canadian Social Insurance Number</rdfs:label>
    <dc:description>The related Person Identifier uses the person's Canadian
        Social Insurance Number.</dc:description>
    <skos:notation>CanadianSIN</skos:notation>
    <skos:prefLabel>Canadian Social Insurance Number</skos:prefLabel>
    <skos:inScheme rdf:resource="http://ceds.ed.gov/terms#C001571"/>
</owl:NamedIndividual>
```

**Generation strategy:** Parse the `sh:in` list from SHACL → resolve each IRI to its
`skos:notation` or `rdfs:label` → randomly select. Zero LLM involvement needed.
This is fast, deterministic, and guaranteed correct.

> **PoC finding (Feb 2026):** Not all concept scheme properties have `sh:in` lists in the
> SHACL. For example, `hasSex` (P000255) and `hasRaceAndEthnicity` (P001943) have
> NO `sh:in` list — their valid values must be resolved by following the property's
> `schema:rangeIncludes` to a concept scheme class, then finding all
> `owl:NamedIndividual` members of that class. See Section 1.1.3 for the two
> resolution strategies.

### 2.2 Literal Value Properties (Need Generated Data)

These are datatype properties whose range is an XSD type (`xsd:string`, `xsd:date`,
`xsd:token`, etc.). The ontology describes what the value *means* but doesn't
enumerate valid values.

**Example — `FirstName` (P000115):**

```xml
<rdf:Property rdf:about="http://ceds.ed.gov/terms#P000115">
    <rdfs:label>First Name</rdfs:label>
    <schema:rangeIncludes rdf:resource="http://www.w3.org/2001/XMLSchema#string" />
    <skos:notation>FirstName</skos:notation>
    <dc:description>The full legal first name given to a person at birth,
        baptism, or through legal change.</dc:description>
    <maxLength>75</maxLength>
    <textFormat>Alphanumeric</textFormat>
</rdf:Property>
```

**Example — `Birthdate` (P000033):**

```xml
<rdf:Property rdf:about="http://ceds.ed.gov/terms#P000033">
    <rdfs:label>Birthdate</rdfs:label>
    <schema:rangeIncludes rdf:resource="http://www.w3.org/2001/XMLSchema#date" />
    <skos:notation>Birthdate</skos:notation>
    <dc:description>The year, month and day on which a person was born.</dc:description>
    <textFormat>YYYY-MM-DD</textFormat>
</rdf:Property>
```

**Generation strategy:** Send the property metadata to a local LLM with a structured
JSON output schema → get back an array of realistic values → cache and draw from them.

---

## 3. Revised Architecture

### 3.1 High-Level Design

```
┌───────────────────────────────────────────────────────────────────┐
│                     SyntheticDataGenerator                        │
│                                                                   │
│  ┌───────────────┐   ┌────────────────────────────────────────┐  │
│  │ ShapeRegistry  │──>│  SHACLIntrospector                     │  │
│  │ (load shape)   │   │  (extract constraints, sh:in lists)   │  │
│  └───────────────┘   └─────────────┬──────────────────────────┘  │
│                                    │                              │
│  ┌─────────────────────────────────┴──────────────────────────┐  │
│  │  OntologyLoader (3 sources → single rdflib Graph)          │  │
│  │  ├── CEDS-Ontology.rdf  (235,570 triples)                 │  │
│  │  ├── Common.ttl          (+60 triples, cepi: shared)       │  │
│  │  └── Person_Extension_Ontology.ttl (+42 triples, per-shape)│  │
│  └─────────────────────────────────┬──────────────────────────┘  │
│                                    │                              │
│                   ┌────────────────┴────────────────┐            │
│                   │                                  │            │
│          ┌────────v─────────┐            ┌──────────v─────────┐  │
│          │  ConceptScheme    │            │  LiteralValue       │  │
│          │  Generator        │            │  Generator          │  │
│          │                   │            │                     │  │
│          │  Strategy A:      │            │  OntologyMetadata   │  │
│          │  sh:in → resolve  │            │  → LLM prompt       │  │
│          │  NamedIndividuals │            │  → structured JSON  │  │
│          │                   │            │  → value cache       │  │
│          │  Strategy B:      │            │                     │  │
│          │  rangeIncludes →  │            │  🤖 Local LLM       │  │
│          │  class → members  │            │                     │  │
│          │                   │            │                     │  │
│          │  ⚡ No LLM needed │            │                     │  │
│          └────────┬─────────┘            └──────────┬─────────┘  │
│                   │                                  │            │
│                   └────────────────┬────────────────┘            │
│                                    │                              │
│                        ┌───────────v────────────┐                │
│                        │  MappingAwareAssembler   │                │
│                        │  reads mapping YAML      │                │
│                        │  assembles CSV rows       │                │
│                        │  handles pipe-delimited   │                │
│                        │  multi-value fields       │                │
│                        └───────────┬────────────┘                │
│                                    │                              │
│                        ┌───────────v────────────┐                │
│                        │  OutputWriter            │                │
│                        │  CSV / NDJSON / JSON-LD  │                │
│                        └────────────────────────┘                │
└───────────────────────────────────────────────────────────────────┘
```

### 3.2 The LLM Value Generation Flow

For literal properties, the LLM generates values in bulk, not per-record:

```
1. Introspect shape → identify all literal properties
2. For each literal property:
   a. Extract metadata from ontology:
      - rdfs:label, dc:description, skos:definition
      - schema:rangeIncludes (XSD datatype)
      - maxLength, textFormat
      - Parent class context (e.g., "PersonName" → education domain)
   b. Build a structured prompt (see Section 4)
   c. Call local LLM with JSON schema constraint
   d. Receive array of N values
   e. Cache the values (keyed by property IRI + shape context)
3. For each record to generate:
   a. For enumerated properties → random.choice(named_individuals)
   b. For literal properties → random.choice(cached_llm_values)
   c. Assemble into CSV row per mapping YAML
```

**Key insight: Generate-then-sample.** We call the LLM once per property to generate
a pool of (e.g.) 200 values, then randomly sample from that pool for each record.
Generating 10,000 records does NOT mean 10,000 LLM calls — it means ~5-10 LLM calls
(one per literal property) that each return 200 values, then pure random selection.

---

## 4. LLM Prompt Design

### 4.1 The Prompt Template

```
You are a synthetic data generator for education data systems.

Generate exactly {count} realistic values for the following CEDS
(Common Education Data Standards) property:

Property: {rdfs:label}
Description: {dc:description}
Definition: {skos:definition}  (if available)
Data Type: {schema:rangeIncludes → human readable}
Format: {textFormat}  (if available)
Max Length: {maxLength}  (if available)
Parent Class: {parent class rdfs:label}

Context: This data is used in US K-12 and postsecondary education records
managed by state education agencies.

Requirements:
- Values must be realistic and diverse (not repetitive)
- Values must conform to the data type and format constraints
- For string values: respect the max length
- For date values: use ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
- For numeric tokens: generate realistic ID numbers
- Return ONLY the JSON array, no explanation

Return your response as a JSON object matching this schema.
```

### 4.2 The JSON Schema Constraint

```json
{
  "type": "object",
  "properties": {
    "values": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 200,
      "maxItems": 200
    }
  },
  "required": ["values"]
}
```

### 4.3 Example: Prompting for "First Name"

**Prompt:**
```
Generate exactly 200 realistic values for the following CEDS property:

Property: First Name
Description: The full legal first name given to a person at birth, baptism,
    or through legal change.
Data Type: string
Format: Alphanumeric
Max Length: 75
Parent Class: PersonName

Context: This data is used in US K-12 and postsecondary education records.
Ensure the names are diverse and representative of US school populations.
```

**Expected LLM response (JSON-constrained):**
```json
{
  "values": [
    "Maria", "James", "Aiden", "Sophia", "DeShawn", "Yuki", "Mohammed",
    "Isabella", "Carlos", "Priya", "Liam", "Aaliyah", "Wei", "Fatima",
    "Connor", "Valentina", "Jayden", "Amara", "Lucas", "Mei-Ling", ...
  ]
}
```

### 4.4 Example: Prompting for "Birthdate"

**Prompt:**
```
Generate exactly 200 realistic values for the following CEDS property:

Property: Birthdate
Description: The year, month and day on which a person was born.
Data Type: date
Format: YYYY-MM-DD
Parent Class: PersonBirth

Context: This data is for K-12 and postsecondary education records.
Generate dates spanning realistic ages for students (5-22) and staff (22-70).
```

**Expected response:**
```json
{
  "values": [
    "2018-03-15", "2012-11-22", "2001-07-08", "1978-01-30", "2015-09-04",
    "1985-12-17", "2010-06-25", "1992-04-11", "2019-02-28", "1970-08-19", ...
  ]
}
```

---

## 5. LLM Runtime Options — Detailed Comparison

### 5.0 Why Not llama-cpp-python? (Original Recommendation — Rejected)

The original version of this research recommended `llama-cpp-python` as the primary
runtime. During the proof-of-concept implementation, we discovered a **blocking issue
on Windows:** `llama-cpp-python` requires C/C++ build tools (Visual Studio Build Tools
or MinGW) to compile from source. While pre-built wheels exist for some configurations,
they are not consistently available for all Python version + CUDA version combinations.

**Why this is a deal-breaker for our users:**
- Our target users are **state education agency data engineers**, not ML researchers.
  Asking them to install Visual Studio Build Tools (6+ GB download) to generate test
  data is hostile to the end-user experience.
- The project's design philosophy (Rule 9: “Design for the End User”) requires that
  `pip install ceds-jsonld[sdg]` work without compilation prerequisites.
- On Linux/macOS, pre-built wheels are more reliable, but Windows is our primary
  platform (see project config: “Python 3.14 on Windows”).

**Result:** We pivoted to `transformers` + `torch`, which have **pre-built wheels
for all major platforms** including Windows + CUDA. This was validated end-to-end
in the proof of concept.

### 5.1 Option A: transformers + torch + huggingface-hub (Recommended — PoC Validated)

| Aspect | Details |
|--------|---------|
| **What** | HuggingFace’s `transformers` library loads full-weight models directly on GPU or CPU via PyTorch |
| **Install** | `pip install transformers torch huggingface-hub` — **pre-built wheels for Windows, Linux, macOS** including CUDA variants |
| **Structured JSON** | Prompt-engineered JSON output + post-parse validation (no grammar-level enforcement, but reliable with good prompting + retry) |
| **Model management** | `AutoModelForCausalLM.from_pretrained()` auto-downloads from HuggingFace Hub to `~/.cache/huggingface/` on first use |
| **Memory (GPU)** | Qwen3 4B BFloat16: ~7.7 GB VRAM. Qwen3 0.6B: ~1.5 GB VRAM. |
| **Memory (CPU)** | Same models run on CPU with Float32, using system RAM instead. Slower but functional. |
| **GPU support** | `torch` ships with CUDA baked into the wheel — `pip install torch` on a CUDA machine Just Works™ |
| **No background service** | Model loads in-process, unloads when code exits — **zero footprint when idle** |
| **Maturity** | `transformers`: 145K+ GitHub stars. `torch`: 90K+ stars. Industry standard. |
| **Downside** | `torch` is a large dependency (~2.7 GB pip wheel with CUDA). See §5.7 for mitigation. |

**Why this is the right default for our users:**
- `pip install ceds-jsonld[sdg]` is the **only install step** — no C compiler, no
  external binary, no background service
- Pre-built wheels exist for **Windows x64, Linux x64, macOS (arm64 + x64)** with
  CUDA 11.8 and 12.4 variants
- The HuggingFace ecosystem is the de facto standard for model distribution — users
  who have done any ML work already have `torch` installed
- **Proven in PoC:** Qwen3 4B loaded in 7.3s, generated 83 tokens at 14 tok/s, produced
  valid JSON-LD on first attempt

**Python usage (as proven in PoC):**
```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

model_id = "Qwen/Qwen3-4B"
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.bfloat16 if device == "cuda" else torch.float32

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=dtype,
    device_map="auto",                    # auto GPU/CPU placement
    attn_implementation="sdpa",           # memory-efficient attention
)

messages = [{"role": "user", "content": prompt}]
inputs = tokenizer.apply_chat_template(
    messages, return_tensors="pt", add_generation_prompt=True,
    enable_thinking=False,                # skip CoT for speed
).to(device)

with torch.no_grad():
    output = model.generate(
        inputs, max_new_tokens=512, temperature=0.8,
        top_p=0.95, repetition_penalty=1.1,
    )
response = tokenizer.decode(output[0][inputs.shape[1]:], skip_special_tokens=True)
# Parse JSON from response
```

### 5.2 Option B: Ollama (Power-User Alternative)

| Aspect | Details |
|--------|---------|
| **What** | Local LLM server with REST API, native structured output support |
| **Install** | Separate binary install: `winget install Ollama.Ollama` + `ollama pull qwen3:4b` |
| **Structured JSON** | Native `format` parameter accepts JSON schema — grammar-constrained at token level |
| **Python client** | `pip install ollama` — 1st-party, Pydantic-friendly |
| **Models** | Pull any GGUF model: `ollama pull qwen3:4b` |
| **GPU support** | Auto-detects CUDA, ROCm, Metal; falls back to CPU |
| **Startup** | Runs as background Windows service — **always on, even when not needed** |
| **Maturity** | 78K+ GitHub stars, massive community |
| **Downside** | Background service consumes ~200MB RAM when idle; keeps last model warm in VRAM; 3-step install process |

**When Ollama makes sense:** For users who already run Ollama for other projects and
want to share the same model cache. Our code auto-detects Ollama via
`shutil.which("ollama")` and uses it if available, preferring it over in-process
loading for faster warm-start times.

**Python usage with structured output:**
```python
from ollama import chat
from pydantic import BaseModel

class GeneratedValues(BaseModel):
    values: list[str]

response = chat(
    model="qwen3:4b",
    messages=[{"role": "user", "content": prompt}],
    format=GeneratedValues.model_json_schema(),
)
result = GeneratedValues.model_validate_json(response.message.content)
# result.values is guaranteed to be list[str] — grammar-enforced
```

### 5.3 Option C: llama-cpp-python (Rejected for Primary Use)

| Aspect | Details |
|--------|---------|
| **What** | Python ctypes bindings to llama.cpp — runs GGUF models in-process |
| **Install** | `pip install llama-cpp-python` — **requires C/C++ build tools on Windows** |
| **Structured JSON** | Native GBNF grammar engine — strongest JSON enforcement available |
| **GGUF models** | Quantized models (Q4_K_M) are ~3x smaller and ~5x faster than full-weight |
| **Downside** | **Build tools required on Windows** — blocks `pip install`-only workflow |

**Why rejected as primary:**
- Windows users must install Visual Studio Build Tools (~6 GB) or MSYS2/MinGW
  before `pip install llama-cpp-python` will compile successfully
- Pre-built wheels on PyPI are inconsistent across Python version + platform combos
- Our target users (education data engineers) should not need a C compiler

**When llama-cpp-python could work:**
- Users on Linux/macOS where pre-built wheels are more reliable
- Power users who already have build tools installed
- Future: if PyPI wheels become consistently available for Windows + CUDA,
  this could be revisited as a lighter-weight alternative to torch

### 5.4 Option D: Outlines (Grammar-Constrained Generation)

| Aspect | Details |
|--------|---------|
| **What** | Library for guaranteed-valid structured generation from any LLM |
| **Install** | `pip install outlines` |
| **Structured JSON** | Compiles JSON schema → finite-state machine → token-level enforcement |
| **Models** | Works with transformers models, vLLM, Ollama, OpenAI |
| **Unique strength** | Can enforce regex patterns, CFG grammars, not just JSON schema |
| **Consideration** | Could layer on top of transformers to add grammar-level JSON enforcement |
| **Stars** | 13.4K |

**Potential future enhancement:** If prompt-engineered JSON output proves unreliable
for certain shapes, Outlines can be added as an optional layer on top of transformers
to provide grammar-level enforcement. Since we already use transformers, adding Outlines
is just `pip install outlines` — no new runtime.

### 5.5 Comparison Matrix (Revised After PoC)

| Criteria | transformers+torch | Ollama | llama-cpp-python | Outlines |
|----------|-------------------|--------|------------------|----------|
| **Install ease (Windows)** | ⭐⭐⭐⭐⭐ (pre-built wheels) | ⭐⭐⭐ (3-step external) | ⭐⭐ (needs C compiler) | ⭐⭐⭐⭐ (pip, uses torch) |
| **`pip install` only** | ✅ everything via pip | ❌ needs external binary | ❌ needs build tools | ✅ pip only |
| **Structured JSON** | ⭐⭐⭐⭐ prompt + parse + retry | ⭐⭐⭐⭐⭐ native GBNF | ⭐⭐⭐⭐⭐ native GBNF | ⭐⭐⭐⭐⭐ FSM-enforced |
| **Background service** | ❌ none (in-process) | ⚠️ always-on Windows svc | ❌ none | ❌ none |
| **Idle footprint** | 0 MB | ~200 MB RAM + VRAM | 0 MB | 0 MB |
| **Model auto-download** | ✅ via huggingface-hub | ❌ manual `ollama pull` | ✅ via huggingface-hub | ✅ via HF |
| **Pip install size** | ~2.7 GB (torch+CUDA) | ~5 MB (client only) | ~25 MB (if it builds) | ~50 MB |
| **VRAM usage (4B model)** | ~7.7 GB (BFloat16) | ~3 GB (Q4 GGUF) | ~3 GB (Q4 GGUF) | ~7.7 GB (full) |
| **Generation speed** | ~14 tok/s (full BF16) | ~80 tok/s (Q4 GGUF) | ~80 tok/s (Q4 GGUF) | ~14 tok/s |
| **CPU fallback** | ✅ auto via device_map | ✅ auto | ✅ auto | ✅ auto |
| **PoC validated** | ✅ **Yes** | Not tested | ❌ Build failed | Not tested |
| **Community** | ⭐⭐⭐⭐⭐ (145K + 90K stars) | ⭐⭐⭐⭐⭐ (78K stars) | ⭐⭐⭐⭐ (10K stars) | ⭐⭐⭐⭐ (13.4K) |

### 5.6 Recommendation: **transformers + torch** (primary) + **Ollama** (auto-detected alternative)

**Primary:** `transformers` + `torch` + `huggingface-hub` as the default LLM runtime.

Reasons:
1. **Single `pip install`** — `pip install ceds-jsonld[sdg]` is the only step. No
   C compiler. No external binary download. No `ollama pull`. No service configuration.
2. **Pre-built wheels everywhere** — PyTorch ships pre-built wheels for Windows x64
   (CUDA 11.8, 12.4), Linux x64, macOS arm64/x64. No compilation step.
3. **No background service** — the model loads when the user's code runs and unloads
   when it finishes. Nothing sits in the system tray eating RAM and VRAM when idle.
4. **Auto-download model** — `AutoModelForCausalLM.from_pretrained()` pulls model
   weights from HuggingFace Hub on first use, cached permanently at
   `~/.cache/huggingface/`. Subsequent loads are ~7s from disk (GPU) or ~30s (CPU).
5. **GPU + CPU transparent** — `device_map="auto"` uses GPU if available, CPU otherwise.
   No code changes needed between GPU and CPU machines.
6. **Industry standard** — 145K+ stars. Users who have done any ML work already have
   torch installed. Same ecosystem as the rest of the HuggingFace toolchain.
7. **PoC validated** — Proven end-to-end with Qwen3 4B on RTX 3090. Generated valid
   Person JSON-LD on first attempt.

**Auto-detected alternative:** If Ollama is already running on the user's machine
(detected via `shutil.which("ollama")` or a quick `httpx.get("http://localhost:11434")`),
prefer it for faster generation (GGUF quantized models are ~5x faster). Power users
who already have Ollama get the best of both worlds.

**Fallback:** If neither `transformers` nor Ollama is available, fall back to cached
values or built-in generators (see Section 8).

### 5.7 Managing the torch Dependency Size

`torch` with CUDA is a ~2.7 GB pip download. This is the primary trade-off vs.
llama-cpp-python (~25 MB). Mitigations:

1. **CPU-only torch is smaller** — `pip install torch --index-url https://download.pytorch.org/whl/cpu`
   is ~200 MB. Users without a GPU can use this.
2. **torch is often already installed** — data scientists, ML engineers, and anyone
   using Jupyter notebooks likely already has torch in their environment.
3. **The download is one-time** — pip caches the wheel. Subsequent installs in new
   venvs are fast from the local cache.
4. **We can document both paths** — GPU users: `pip install ceds-jsonld[sdg]`.
   CPU-only users: install CPU torch first, then `pip install ceds-jsonld[sdg]`.
5. **The `[sdg]` extra is optional** — users who don't need synthetic data generation
   never install torch at all. The core library stays lightweight.

### 5.8 Hardware Requirements & Recommendations

#### GPU (Recommended for Development)

| Hardware | Minimum | Recommended | Tested |
|----------|---------|-------------|--------|
| **GPU** | NVIDIA with 4+ GB VRAM | NVIDIA with 8+ GB VRAM | RTX 3090 (24 GB) |
| **CUDA** | 11.8+ | 12.4+ | 12.4 |
| **System RAM** | 8 GB | 16 GB | 32+ GB |
| **Disk** | 15 GB free (torch + model) | 20 GB free | — |

GPU generation speed with Qwen3 4B (BFloat16):
- **RTX 3090 (24 GB):** ~14 tok/s — measured in PoC
- **RTX 4090 (24 GB):** ~25-30 tok/s estimated (Ada architecture)
- **RTX 3060 (12 GB):** ~8-10 tok/s estimated (fits 4B model in BF16)
- **RTX 3050 (8 GB):** Use Qwen3 0.6B (~1.5 GB VRAM) or run 4B in Float16 with offloading

#### CPU (Fallback — Slower but Functional)

| Hardware | Minimum | Recommended |
|----------|---------|-------------|
| **CPU** | Any x64 with AVX2 | Modern multi-core (8+ cores) |
| **System RAM** | 16 GB (for 4B model in Float32: ~16 GB) | 32 GB |
| **Disk** | 15 GB free | 20 GB free |

CPU generation speed estimates:
- **4B model (Float32):** ~1-2 tok/s — usable for one-time cache generation
- **0.6B model (Float32):** ~10-15 tok/s — reasonable for interactive use
- **Recommendation:** For CPU-only machines, use Qwen3 0.6B or rely on cached values

#### No GPU, No Large RAM — Use Cache or Fallback

For CI environments and constrained machines:
- **Tier 2 (cached values):** Zero hardware requirements beyond running Python
- **Tier 3 (fallback generators):** Zero hardware requirements, zero external deps
- Ship pre-warmed cache files with the package for zero-setup CI

#### Supported PyTorch Versions

| Package | Minimum | Tested | Notes |
|---------|---------|--------|-------|
| `torch` | >=2.2 | 2.6.0+cu124 | BFloat16 + SDPA attention require 2.0+; 2.2+ recommended for stability |
| `transformers` | >=4.40 | 5.1.0 | Qwen3 support added in ~4.40; 5.x is current stable |
| `huggingface-hub` | >=0.20 | 1.4.1 | Model auto-download + caching |
| Python | >=3.12 | 3.12.4 | Matches project requirement |

#### CUDA Compatibility Note

PyTorch wheels on PyPI bundle CUDA runtime libraries, so users do **not** need to
install the NVIDIA CUDA Toolkit separately. `pip install torch` on a machine with an
NVIDIA GPU Just Works. The only prerequisite is an up-to-date NVIDIA driver:
- **Minimum driver:** 525.60+ (for CUDA 12.x wheels)
- **Check driver:** `nvidia-smi` in terminal — shows driver version and CUDA version

---

## 6. Model Selection for Structured JSON Generation

### 6.1 The Task Characteristics

Our generation task is:
- **Low complexity** — generating lists of names, dates, IDs (not reasoning or coding)
- **Highly constrained** — output must match a JSON schema exactly
- **Batch-oriented** — one call per property type, requesting 200 values
- **Domain-specific** — education context, US demographics
- **Prompt is short** — ~200 tokens input, ~2000 tokens output

This means we want: **small, fast, instruction-following models with strong JSON adherence.**

### 6.2 Recommended Models

| Model | Size | VRAM | Speed (est.) | JSON Quality | Notes |
|-------|------|------|-------------|-------------|-------|
| **Qwen3 4B** | 2.6GB Q4 / 8.2GB full | ~3GB Q4 / ~7.7GB full | ~80 tok/s (Q4 est.) / **14 tok/s (full, measured)** | ⭐⭐⭐⭐⭐ | Best small model for structured output; native tool calling; thinking mode can be disabled for speed |
| **Phi-4 Mini 3.8B** | 2.4GB Q4 | ~3GB | ~90 tok/s (est.) | ⭐⭐⭐⭐ | Microsoft's small model, strong instruction following |
| **Llama 3.2 3B** | 2.0GB Q4 | ~2.5GB | ~100 tok/s (est.) | ⭐⭐⭐⭐ | Meta's efficient small model |
| **Granite4 3B** | 2.0GB Q4 | ~2.5GB | ~100 tok/s (est.) | ⭐⭐⭐⭐⭐ | IBM's model, specifically optimized for tool calling and structured output |
| **Granite4 1B** | 0.7GB Q4 | ~1GB | ~200 tok/s (est.) | ⭐⭐⭐ | Ultra-light option for CI; may need retry on complex properties |
| **FunctionGemma 270M** | 0.2GB | ~0.5GB | ~500 tok/s (est.) | ⭐⭐⭐ | Google's function-calling specialist at 270M params; experimental but ultra-fast |
| **Qwen3 0.6B** | 0.5GB Q4 | ~0.8GB | ~300 tok/s (est.) | ⭐⭐⭐ | Smallest model with thinking capability; may struggle with diverse names |

> **PoC note:** The measured 14 tok/s for Qwen3 4B is with **full BFloat16 weights via
> transformers** (not GGUF quantized via llama-cpp-python). GGUF Q4 quantization would
> be ~5x faster (~80 tok/s), but llama-cpp-python requires C build tools on Windows
> (see §5.0), so the production implementation uses `transformers` + `torch` directly.
> If Ollama is auto-detected, it will use GGUF models for faster generation.

### 6.3 Recommended Default: **Qwen3 4B** or **Granite4 3B**

- **Qwen3 4B** — Best overall quality for structured JSON. Its `/no_think` mode
  skips chain-of-thought and goes straight to the answer, which is exactly what we want
  for "give me 200 first names as JSON".
- **Granite4 3B** — IBM specifically optimized this for tool calling and structured
  output. Strong JSON schema adherence at small size.
- Make the model configurable — `--model qwen3:4b` flag on CLI, environment variable
  `CEDS_SYNTH_MODEL`, or constructor parameter.

### 6.4 Model Delivery

With `transformers`, models auto-download from HuggingFace Hub on first use.
The user never runs a separate command — the library handles it transparently:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

model_id = "Qwen/Qwen3-4B"  # ~8 GB full weights, auto-cached
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.bfloat16 if device == "cuda" else torch.float32

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=dtype,
    device_map="auto",
    attn_implementation="sdpa",
)
```

Recommended model repo IDs (full-weight, for transformers):
```
Qwen/Qwen3-4B                 # ~8 GB full weights — recommended GPU default
Qwen/Qwen3-0.6B               # ~1.2 GB full weights — CPU or low-VRAM option
microsoft/Phi-4-mini           # ~7.6 GB — Microsoft alternative
ibm-granite/granite-3b         # ~6 GB — alternative, JSON-specialized
```

The model is configurable via `--model` CLI flag, `CEDS_SYNTH_MODEL` env var,
or `SyntheticDataGenerator(model="...")` constructor parameter.

For users who already have Ollama installed, GGUF-quantized models are faster:
```bash
ollama pull qwen3:4b  # ~2.6 GB Q4 GGUF, ~80 tok/s vs ~14 tok/s full-weight
```

---

## 7. Caching Strategy

### 7.1 Why Cache?

LLM calls are slow (1-5 seconds each). For CI and repeated runs, we don't want to
re-generate the same value pools. Cache the generated values per property.

### 7.2 Cache Design

```
~/.ceds_jsonld/cache/
  synthetic_values/
    person/
      P000115_FirstName_200.json     # 200 first names
      P000172_LastOrSurname_200.json  # 200 last names
      P000033_Birthdate_200.json      # 200 birthdates
      P000121_GenerationCodeOrSuffix_200.json
    organization/
      P000204_OrganizationName_200.json
      ...
```

Each cache file:
```json
{
  "property_iri": "http://ceds.ed.gov/terms#P000115",
  "property_label": "First Name",
  "model": "qwen3:4b",
  "generated_at": "2026-02-08T14:30:00",
  "count": 200,
  "values": ["Maria", "James", "Aiden", ...]
}
```

### 7.3 Cache Behavior

| Scenario | Behavior |
|----------|----------|
| Cache file exists and has enough values | Use cached values (no LLM call) |
| Cache file missing | Generate via LLM, save to cache |
| `--no-cache` flag | Always regenerate |
| `--cache-size N` | Generate N values per property (default: 200) |
| Different model requested | Regenerate (model name is part of cache key) |

### 7.4 Pre-warming

For CI, ship a pre-generated cache in the repo:
```bash
ceds-jsonld generate-cache --shape person --count 200 --seed 42
# Creates deterministic cache files that can be committed to the repo
```

This means CI environments **need no LLM runtime at all** — they use the
pre-warmed cache with deterministic values.

---

## 8. Fallback Strategy (No LLM Available)

The generator MUST work even without `llama-cpp-python` installed. Three-tier fallback:

### Tier 1: LLM Available → In-Process Generation (transformers+torch or Ollama)
Best quality. Generates contextually-appropriate values based on ontology metadata.
Uses `transformers` + `torch` in-process by default (full-weight models, GPU or CPU).
If Ollama is detected running locally, uses that instead (faster generation with GGUF
quantized models, grammar-enforced JSON).

### Tier 2: Cache Available → Cached Values  
Good quality. Uses previously-generated LLM values from disk cache.
Ship default cache files in the package for the Person shape.

### Tier 3: No LLM, No Cache → Built-in Fallback Generators
Acceptable quality. Use simple rule-based generators:

```python
FALLBACK_GENERATORS: dict[str, Callable] = {
    "xsd:string": lambda prop_name, rng: _fallback_string(prop_name, rng),
    "xsd:date": lambda prop_name, rng: _fallback_date(rng),
    "xsd:dateTime": lambda prop_name, rng: _fallback_datetime(rng),
    "xsd:token": lambda prop_name, rng: str(rng.randint(100000000, 999999999)),
    "xsd:integer": lambda prop_name, rng: str(rng.randint(1, 999999)),
    "xsd:boolean": lambda prop_name, rng: rng.choice(["true", "false"]),
    "xsd:decimal": lambda prop_name, rng: f"{rng.uniform(0, 100):.2f}",
}

# Name-aware string fallbacks (no external dependency)
_STRING_FALLBACKS: dict[str, list[str]] = {
    "FirstName": ["James", "Maria", "Aiden", "Sophia", "Liam", "Olivia",
                   "Noah", "Emma", "Carlos", "Priya", "Wei", "Fatima"],
    "LastOrSurname": ["Smith", "Johnson", "Williams", "Brown", "Jones",
                       "Garcia", "Martinez", "Anderson", "Taylor", "Lee"],
    "MiddleName": ["Marie", "James", "Lee", "Ann", "Ray", "Grace"],
    "GenerationCodeOrSuffix": ["Jr", "Sr", "II", "III", "IV", "V", ""],
}
```

This tier has **zero external dependencies** — pure Python stdlib `random` module.
It's less realistic than LLM-generated data but produces valid, pipeline-compatible
output.

---

## 9. Concept Scheme Value Extraction

### 9.1 How It Works

For `sh:in`-constrained properties, we already have everything we need. The process:

1. **From SHACL:** `PropertyInfo.allowed_values` gives us the list of IRIs
   (e.g., `["ceds:NI001571173132", "ceds:NI001571173129", ...]`)

2. **From the ontology RDF:** Resolve each IRI to its human-readable form:
   - `skos:notation` → the short code (e.g., `"CanadianSIN"`, `"District"`)
   - `rdfs:label` → the human label (e.g., `"Canadian Social Insurance Number"`)
   - `skos:prefLabel` → the preferred label

3. **For generation:** Randomly select from the resolved list. The mapping YAML's
   `transform` field tells us whether to use the full IRI prefix form
   (e.g., `"PersonIdentificationSystem_CanadianSIN"`) or the short form.

### 9.2 Implementation — Two Resolution Strategies

**Strategy A: `sh:in` present (explicit enumeration):**

When the SHACL property has an `sh:in` list, resolve each IRI directly from the
ontology using `skos:notation`:

```python
def resolve_named_individuals(
    ontology: Graph, iris: list[URIRef]
) -> list[str]:
    """Resolve sh:in IRI list to skos:notation values."""
    values = []
    for iri in iris:
        notation = ontology.value(iri, SKOS.notation)
        if notation:
            values.append(str(notation))
        else:
            label = ontology.value(iri, RDFS.label)
            values.append(str(label) if label else iri.split("#")[-1])
    return values
```

**Strategy B: No `sh:in`, range is a concept scheme class:**

When the SHACL property has no `sh:in`, follow the property's `schema:rangeIncludes`
to find the concept scheme class, then enumerate all `owl:NamedIndividual` members:

```python
def resolve_concept_scheme_members(
    ontology: Graph, class_iri: URIRef
) -> list[str]:
    """Find all NamedIndividuals of a concept scheme class."""
    values = []
    for individual in ontology.subjects(RDF.type, class_iri):
        if (individual, RDF.type, OWL.NamedIndividual) in ontology:
            notation = ontology.value(individual, SKOS.notation)
            if notation:
                values.append(str(notation))
    return values
```

**Combined ConceptSchemeResolver:**

```python
class ConceptSchemeResolver:
    """Resolve concept scheme values from SHACL + ontology."""

    def __init__(self, ontology_graph: Graph) -> None:
        self._graph = ontology_graph

    def resolve(self, property_info: PropertyInfo) -> list[str]:
        """Resolve values using the appropriate strategy."""
        if property_info.allowed_values:  # Strategy A: sh:in present
            return resolve_named_individuals(
                self._graph, property_info.allowed_values
            )
        elif property_info.node_class:  # Strategy B: class-based
            range_class = self._get_range_class(property_info.path)
            if range_class:
                return resolve_concept_scheme_members(
                    self._graph, range_class
                )
        return []

    def _get_range_class(self, property_iri: URIRef) -> URIRef | None:
        """Get the concept scheme class from schema:rangeIncludes."""
        for range_cls in self._graph.objects(
            property_iri, SCHEMA.rangeIncludes
        ):
            # Skip XSD types — we want concept scheme classes
            if "XMLSchema" not in str(range_cls):
                return range_cls
        return None
```

> **PoC validation:** This dual-strategy approach was proven in the
> `bench_person_jsonld_dynamic.py` proof of concept. The Person shape has 3 concept
> scheme properties: `hasPersonIdentificationSystem` (Strategy A: 21 values from
> `sh:in`), `hasSex` (Strategy B: 3 values from C000255), and
> `hasRaceAndEthnicity` (Strategy B: 8 values from C001943).

**Performance note:** Loading all three ontology sources (CEDS-Ontology.rdf +
Common.ttl + Person_Extension_Ontology.ttl = 235,672 triples) into an rdflib Graph
takes ~9 seconds. We do this once at generator init time, not per record. This is
fine — it's the same load we already do for SHACL introspection. The load time
could be reduced by caching the parsed graph or using a binary serialization format.

---

## 10. Complete Generation Flow — Person Shape Example

Let's trace through generating 100 Person CSV rows:

### Step 1: Load Shape + Ontology

```python
gen = SyntheticDataGenerator(model="Qwen/Qwen3-4B-GGUF")

# Internally:
# - Loads Person_SHACL.ttl via SHACLIntrospector
# - Loads person_mapping.yaml
# - Loads CEDS-Ontology.rdf into rdflib Graph (for NamedIndividual resolution)
# - On first use: auto-downloads model GGUF to ~/.cache/huggingface/ (~2.6GB)
# - On subsequent uses: loads model from cache in ~3 seconds
```

### Step 2: Classify Properties

| Property | Type | Strategy |
|----------|------|----------|
| `FirstName` (P000115) | `xsd:string` | LLM → "Generate 200 first names" |
| `LastOrSurname` (P000172) | `xsd:string` | LLM → "Generate 200 last names" |
| `MiddleName` (P000184) | `xsd:string` | LLM → "Generate 200 middle names" |
| `GenerationCodeOrSuffix` (P000121) | `xsd:string` | LLM → "Generate 200 name suffixes" |
| `Birthdate` (P000033) | `xsd:date` | LLM → "Generate 200 birthdates" |
| `hasSex` (P000255 → range C000255) | Concept Scheme | Random from class NamedIndividuals (no `sh:in`; use Strategy B) |
| `hasRaceAndEthnicity` (P001943 → range C001943) | Concept Scheme | Random from class NamedIndividuals (no `sh:in`; use Strategy B) |
| `hasPersonIdentificationSystem` (P001571) | Concept Scheme | Random from sh:in list (21 values) |
| `hasPersonIdentifierType` (P001573) | Concept Scheme | Random from NamedIndividuals |
| `PersonIdentifier` (P001572) | `xsd:token` | LLM → "Generate 200 person ID numbers" |

### Step 3: Generate Value Pools

**LLM calls (5-6 calls, ~2-5 seconds each, parallelizable):**
- Call 1: 200 first names → cache
- Call 2: 200 last names → cache
- Call 3: 200 middle names → cache
- Call 4: 200 suffixes → cache
- Call 5: 200 birthdates → cache
- Call 6: 200 person ID tokens → cache

**Concept scheme lookups (instant, from ontology):**
- Sex values: resolve from NamedIndividuals of C000255 → `["Female", "Male", "NotSelected"]`
- Race values: resolve from NamedIndividuals of C001943 → 8 race/ethnicity values
- ID systems: resolve 21 sh:in IRIs → `["CanadianSIN", "District", ...]`
- ID types: resolve from NamedIndividuals

### Step 4: Assemble CSV Rows (100 rows)

For each row, random.choice from the value pools:
```python
{
    "FirstName": random.choice(first_names_pool),      # "Maria"
    "MiddleName": random.choice(middle_names_pool),     # "Elena"  (70% chance)
    "LastName": random.choice(last_names_pool),          # "Gonzalez"
    "GenerationCodeOrSuffix": random.choice(suffix_pool), # ""  (70% chance)
    "Birthdate": random.choice(birthdates_pool),         # "1998-04-15"
    "Sex": random.choice(sex_values),                    # "Female"
    "RaceEthnicity": ",".join(random.sample(race_values, k=rng.randint(1,3))),
    "PersonIdentifiers": "|".join(id_pool_sample),       # pipe-delimited
    "IdentificationSystems": "|".join(sys_pool_sample),
    "PersonIdentifierTypes": "|".join(type_pool_sample),
}
```

**Total time:** ~15-30 seconds for the LLM calls (one-time), then milliseconds to
assemble 100 rows. Second run with cache: milliseconds total.

---

## 11. Pros & Cons of LLM-Assisted Approach

### Pros

| Advantage | Details |
|-----------|---------|
| **Truly generic** | Add any new CEDS shape, and the generator works automatically — the LLM reads the ontology metadata and generates appropriate values. No per-shape code needed. |
| **Contextually realistic** | LLM understands "First Name in education records" produces diverse US student names, not random words. Faker's `fake.first_name()` is generic, not domain-aware. |
| **No Faker dependency** | One fewer library to maintain. `random` + `transformers` is the industry standard for local LLM. |
| **Self-documenting** | The prompt IS the specification. Reading the prompt tells you exactly what values are expected. |
| **Multi-language support** | For localized CEDS deployments, the LLM can generate names in Spanish, Mandarin, etc. Faker requires locale installation. |
| **Future-proof** | As shapes get more complex properties (addresses, course names, assessment titles), the LLM handles them without new code. |
| **Concept scheme handling is free** | For enumerated properties (the majority of object properties), we need zero LLM — just random.choice from the ontology. |

### Cons

| Disadvantage | Impact | Mitigation |
|--------------|--------|------------|
| **Model download on first use** | Medium — ~8 GB one-time download (full weights); ~2.6 GB if using Ollama GGUF | Auto-downloads with progress bar. Cached permanently. Ship pre-warmed value cache for CI. |
| **Non-deterministic by default** | Medium for tests | Seed the RNG for row assembly. LLM-generated pools are cached deterministically. |
| **LLM cold start is slow** | ~7s model load from disk (GPU) | Cache eliminates most LLM calls. Only ~6 calls per shape, ever. |
| **LLM can produce bad values** | Low — prompt engineering + retry handles this | Validate values post-generation: check maxLength, date format, etc. Retry once on failure. |
| **Larger pip install** | ~2.7 GB for torch+CUDA | CPU-only torch is ~200 MB. Most ML users already have torch. `[sdg]` extra is optional. |
| **Can't use in air-gapped CI** | Medium | Ship cache files in repo. Fallback generators work offline with zero deps. |
| **More complex than Faker** | Medium | Clean abstraction layers. Each tier is independent and testable. |

### Cons We're NOT Worried About

| Non-Issue | Why |
|-----------|-----|
| **LLM performance** | We make 5-10 calls total per shape, not per record. Cached after first run. |
| **LLM accuracy** | We're generating names and dates, not solving math. Even a 1B model excels at this. |
| **Cost** | Local LLM = zero API cost. Ollama is free and open source. |
| **Privacy** | Data never leaves the machine. No cloud API calls. |

---

## 12. Comparison: LLM Approach vs. Original Faker Approach

| Dimension | Faker Approach (v1 Research) | LLM Approach (This Research) |
|-----------|------------------------------|------------------------------|
| **New shape support** | Must add property-specific generators in code for each shape | Automatic — reads ontology metadata |
| **Value quality** | Generic (`fake.first_name()` = any culture) | Domain-specific (diverse US education names) |
| **Concept schemes** | Hard-coded lists in a `CEDSProvider` class | Direct from ontology NamedIndividuals — always in sync |
| **Dependencies** | `faker` (~3MB, pure Python) | `transformers` + `torch` + `huggingface-hub` (~2.7GB with CUDA; ~200MB CPU-only) |
| **CI friendliness** | Always works (no LLM needed) | Ship pre-warmed cache for CI; fallback generators for zero-dep mode |
| **Speed (first run)** | Instant | ~30-60s for LLM value pool generation on GPU (one-time, cached) |
| **Speed (cached run)** | Instant | Instant (same as Faker — just random.choice) |
| **Maintenance burden** | Must update when shapes change | Zero — ontology metadata drives everything |
| **Offline support** | Full | Full (with cache or fallback generators) |

**Winner:** The LLM approach is superior for a library that will support 20+ shapes.
Writing custom Faker providers for each shape's properties doesn't scale. Reading the
ontology metadata does.

---

## 12.1 Reusing Existing Library Components

The SDG must build on top of existing `ceds_jsonld` components, not reimplement them.
This section maps what already exists to what the SDG needs.

### What `SHACLIntrospector` Already Provides

| Capability | API | SDG Consumer |
|-----------|-----|-------------|
| Full shape tree with nested children | `shape_tree()` → `NodeShapeInfo` | `classify_properties()` walks this tree |
| Individual shape lookup | `get_shape(name)` → `NodeShapeInfo` | Look up child shapes (PersonNameShape, etc.) |
| Property path IRIs | `PropertyInfo.path` | `OntologyMetadataExtractor` uses these to query RDF |
| sh:in allowed value IRIs | `PropertyInfo.allowed_values` | `ConceptSchemeResolver` Strategy A input |
| Node class identification | `PropertyInfo.node_class` | `ConceptSchemeResolver` Strategy B + structural shape filtering (C200411/C200410) |
| Datatype (xsd:string, etc.) | `PropertyInfo.datatype` | `FallbackGenerators` type routing |
| Cardinality | `PropertyInfo.min_count`, `max_count` | `MappingAwareAssembler` multi-value handling |
| Context reverse lookup (IRI→name) | `_build_iri_to_name()` (currently private) | LLM prompt building, CSV column naming |

### Action Items for Production Implementation

1. **Make `_build_iri_to_name()` public** — Extract to `ceds_jsonld.utils.build_iri_to_name(context)` or
   promote to a public method `SHACLIntrospector.build_iri_to_name()`. Both the mapping template
   generator and the SDG need this utility. The PoC reimplemented it from scratch — unnecessary duplication.

2. **Structural shape filtering** — The introspector's `_build_property_template()` already checks for
   RecordStatus (`C200411`) and DataCollection (`C200410`) node classes. The SDG's `classify_properties()`
   should reuse this logic rather than maintaining its own `STRUCTURAL_PROP_CLASSES` set.

3. **Data flow** — All new SDG components receive `PropertyInfo` / `NodeShapeInfo` as input. They
   do NOT re-parse SHACL Turtle files. The single entry point is:
   ```
   ShapeRegistry.load_shape("person")
     → SHACLIntrospector(shacl_path)
       → shape_tree() → NodeShapeInfo with PropertyInfo list
         → ConceptSchemeResolver.resolve(PropertyInfo)
         → OntologyMetadataExtractor.extract(PropertyInfo.path)
         → FallbackGenerators.generate(PropertyInfo.datatype)
   ```

### What the Introspector Does NOT Provide (Genuinely New)

| Capability | Why It's New | New Component |
|-----------|-------------|---------------|
| Load ontology RDF (CEDS-Ontology.rdf + Common.ttl + extensions) | Introspector only parses SHACL Turtle | `OntologyLoader` |
| Resolve NamedIndividual IRIs → skos:notation values | Requires ontology graph, not SHACL | `ConceptSchemeResolver` |
| Extract rdfs:label, dc:description, maxLength, textFormat | Metadata lives in ontology RDF, not SHACL | `OntologyMetadataExtractor` |
| Class-based concept scheme resolution (Strategy B) | Requires querying owl:NamedIndividual members | `ConceptSchemeResolver` |
| LLM-driven value generation | Entirely new capability | `LLMValueGenerator` |
| CSV row assembly from mapping YAML | New assembly logic | `MappingAwareAssembler` |

---

## 13. Implementation Plan — Revised Task Breakdown

### Phase 1: Core Generator — Concept Schemes + Fallback (Est. ~2 sessions)

| # | Task | Details |
|---|------|---------|
| 1.1 | `ConceptSchemeResolver` class | Parse ontology RDF, resolve `sh:in` IRIs to notation/label values. **Consumes** `PropertyInfo.allowed_values` and `PropertyInfo.node_class` from `SHACLIntrospector` — does NOT re-parse SHACL. |
| 1.2 | `FallbackGenerators` module | Pure-Python generators for all XSD types + name-aware string defaults. Uses `PropertyInfo.datatype` to route to correct generator. |
| 1.3 | `MappingAwareAssembler` class | Read mapping YAML, assemble CSV rows, handle pipe-delimited multi-value. Reuses `SHACLIntrospector.shape_tree()` for structural shape identification (RecordStatus/DataCollection via C200411/C200410). |
| 1.4 | `SyntheticDataGenerator` class | Core orchestrator with concept scheme + fallback generation. Uses existing `ShapeRegistry.load_shape()` → `SHACLIntrospector` → `PropertyInfo` pipeline. |
| 1.5 | CSV + NDJSON output writers | Write to file or stdout |
| 1.6 | Tests: round-trip through Pipeline | Generate CSV → Pipeline → JSON-LD → validate SHACL → pass |

### Phase 2: LLM Integration (Est. ~2 sessions)

| # | Task | Details |
|---|------|---------|
| 2.1 | Add `transformers` + `torch` + `huggingface-hub` to `[sdg]` extras | `pip install ceds-jsonld[sdg]` |
| 2.2 | `OntologyMetadataExtractor` class | Extract rdfs:label, dc:description, maxLength, rangeIncludes from ontology for each property. **Consumes** `PropertyInfo.path` from `SHACLIntrospector`. |
| 2.3 | `LLMValueGenerator` class | Build prompts from metadata, call transformers with JSON schema, parse responses; auto-detect Ollama as alternative |
| 2.4 | Caching layer | File-based cache under `~/.ceds_jsonld/cache/` with model-keyed entries |
| 2.5 | Three-tier fallback logic | LLM (in-process or Ollama) → cache → fallback generators |
| 2.6 | Post-generation validation | Verify LLM values match datatype constraints (maxLength, date format, etc.) |
| 2.7 | Tests: LLM value quality | Test with live LLM if `[sdg]` installed, skip gracefully if not |

### Phase 3: CLI + Integration (Est. ~1-2 sessions)

| # | Task | Details |
|---|------|---------|
| 3.1 | `generate-sample` CLI command | All options: shape, count, format, model, seed, cache control |
| 3.2 | `generate-cache` CLI command | Pre-warm cache for CI environments |
| 3.3 | Ship default Person cache | Commit pre-generated cache files for zero-setup CI |
| 3.4 | Streaming mode | Iterator/generator pattern for 100K+ records |
| 3.5 | Integration tests | End-to-end: CLI → CSV → Pipeline → validate |
| 3.6 | Documentation | Sphinx docs, README examples, getting-started guide for Ollama setup |

### Phase 4: Polish (Est. ~1 session)

| # | Task | Details |
|---|------|---------|
| 4.1 | Benchmark | Time: LLM generation, cached generation, 10K/100K/1M row assembly |
| 4.2 | Model comparison | Test Qwen3 4B vs. Granite4 3B vs. Phi-4 Mini for value quality |
| 4.3 | JSON-LD output mode | Generate rows → Pipeline → JSON-LD documents |
| 4.4 | Distribution profiles | Optional YAML config for demographic distributions |

---

## 14. Installation & End-User Experience

### 14.1 The `[sdg]` Extras Group

Following the project's existing extras pattern (`[cli]`, `[excel]`, `[cosmos]`, etc.):

```toml
# In pyproject.toml [project.optional-dependencies]
sdg = ["torch>=2.2", "transformers>=4.40", "huggingface-hub>=0.20"]
```

**For the end user (GPU machine with NVIDIA):**
```bash
pip install ceds-jsonld[sdg]
```

**For CPU-only machines (smaller download):**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install ceds-jsonld[sdg]
```

That's it. No C compiler. No external binary. No service configuration.

### 14.2 What the User Types (Python API)

```python
from ceds_jsonld import Pipeline, SyntheticDataGenerator

# First run: auto-downloads model (~8 GB for Qwen3-4B) with progress bar
# Subsequent runs: loads from ~/.cache/huggingface/ in ~7 seconds (GPU)
gen = SyntheticDataGenerator(shape="person")
gen.to_csv(count=500, output="test_data.csv")

# Or as a one-liner through Pipeline
pipeline = Pipeline.from_shape("person")
docs = pipeline.run_synthetic(count=100)  # generates CSV → runs full pipeline
```

### 14.3 What the User Types (CLI)

```bash
# First run prints: "Downloading model Qwen3-4B (8.0 GB)... done."
# Subsequent runs print: "Loading model from cache... done (7.3s)."
ceds-jsonld generate-sample --shape person --count 500 --output test_data.csv

# Pre-warm the value cache (e.g., before committing cache files for CI)
ceds-jsonld generate-cache --shape person --count 200

# Force CPU-only mode (for machines without NVIDIA GPU)
ceds-jsonld generate-sample --shape person --count 50 --device cpu
```

### 14.4 What Happens Under the Hood

1. Check if value cache exists for this shape+model → if yes, use it (instant, no LLM)
2. Check if Ollama is running locally → if yes, use it (fastest: GGUF quantized)
3. Load model in-process via `transformers` + `torch` → auto-download from HuggingFace if needed
4. Auto-detect GPU vs CPU → use BFloat16 on CUDA, Float32 on CPU
5. Generate value pools (~6 LLM calls for Person, ~30-60s total on GPU, longer on CPU)
6. Save value pools to `~/.ceds_jsonld/cache/` for next time
7. **Unload model** — RAM freed, GPU freed, nothing running
8. Assemble CSV rows from cached pools (milliseconds)

### 14.5 Dependency Impact

| Package | Size | Required? | When |
|---------|------|-----------|------|
| `torch` (with CUDA) | ~2.7 GB pip wheel | Optional (`[sdg]` extra) | LLM generation (Tier 1) |
| `torch` (CPU-only) | ~200 MB pip wheel | Optional (manual install) | CPU-only machines |
| `transformers` | ~10 MB pip | Optional (`[sdg]` extra) | Model loading + generation |
| `huggingface-hub` | ~5 MB pip | Optional (`[sdg]` extra) | Model auto-download |
| Model weights | ~8 GB (Qwen3-4B, auto-cached) | Auto-downloaded on first use | Stored in `~/.cache/huggingface/` |
| No new deps for Tier 2/3 | — | — | Cache files + stdlib `random` |
| **NOT adding `faker`** | — | — | Replaced by LLM + fallback generators |
| **NOT requiring Ollama** | — | — | Auto-detected as optional alternative |
| **NOT using `llama-cpp-python`** | — | — | Requires C build tools on Windows (see §5.0) |

---

## 15. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `llama-cpp-python` requires C build tools on Windows | **High** | **Rejected as primary.** Use `transformers` + `torch` instead (pre-built wheels). See §5.0. |
| `torch` is a large pip download (~2.7 GB with CUDA) | Medium | CPU-only wheel is ~200 MB. Most ML users already have torch. `[sdg]` extra is optional. |
| No LLM runtime in CI | High | Ship pre-warmed value cache. Fallback generators need zero deps. |
| Model download fails (network) | Medium | Cache persists across runs. Ship default cache in package. Fallback generators as safety net. |
| LLM generates inappropriate values | Low | Post-validation checks. Education-context prompt. Cache review before shipping. |
| LLM generates duplicate values | Low | Request 200 values, deduplicate, fall back to generating more if needed. |
| Model generates non-UTF-8 characters | Very Low | JSON schema constraint enforces string type. Post-validate encoding. |
| `llama-cpp-python` wheel not available for platform | ~~Low~~ **High on Windows** | ~~Pre-built wheels cover Windows x64, Linux x64, macOS. Ollama fallback for exotic platforms.~~ **Rejected as primary — requires C build tools on Windows.** Use `transformers` + `torch` instead. Ollama as auto-detected alternative. |
| Large ontology RDF load time | Low | ~3-5 seconds one-time. Cache the parsed Graph. |
| New shape has properties with no ontology metadata | Medium | Fallback to generic string generation. Log a warning. |

---

## 16. Open Questions for Discussion

### Resolved Questions

1. ~~**Should we use `ollama` Python client or just `httpx` + Ollama REST API?**~~
   - **Resolved:** Neither as primary. Use `transformers` + `torch` for in-process
     execution (no server needed). Auto-detect Ollama as an alternative for power users
     who already have it running.

2. ~~**Should this be a separate extras install?**~~
   - **Resolved:** Yes. `pip install ceds-jsonld[sdg]` installs `torch`, `transformers`,
     and `huggingface-hub`. Follows the existing pattern of `[cli]`, `[excel]`, `[cosmos]`.

3. ~~**What about the Ollama background service problem?**~~
   - **Resolved:** `transformers` runs in-process — model loads when code runs,
     unloads when code exits. Zero footprint when idle. No background service, no tray
     icon, no VRAM held. Ollama is only used when it's already running.

3b. ~~**What about llama-cpp-python as the primary runtime?**~~
   - **Resolved (Feb 2026):** Rejected. `llama-cpp-python` requires C/C++ build tools
     on Windows (Visual Studio Build Tools or MinGW). Pre-built wheels are inconsistent
     across Python + platform combinations. Our end users (education data engineers)
     should not need a C compiler. Pivoted to `transformers` + `torch` which have
     reliable pre-built wheels for all platforms. Validated end-to-end in PoC.

### Open Questions

4. **How many values should we generate per LLM call?**
   - Recommendation: 200 per call. Big enough for diverse sampling, small enough for
     fast LLM response (~2000 tokens output). Configurable via `--cache-size`.

5. **Should we allow cloud LLM providers as an alternative?**
   - Recommendation: Yes, as a future extension. `transformers` supports the same
     models available via cloud providers, and the prompt format is portable.
     But local-first for privacy (education data context).

6. **Should we pre-ship cache files for all shapes or just Person?**
   - Recommendation: Ship Person cache immediately. Add other shapes as they're created.
     Provide `generate-cache` CLI command for users to generate their own.

7. **Should the LLM prompt include the parent shape context (e.g., "this is a Person record")?**
   - Recommendation: Yes. The parent class label adds important context. "Generate first
     names for a PersonName in K-12 education records" is much better than "Generate
     first names."

8. **What about `faker` as a fallback instead of hardcoded lists?**
   - Recommendation: No. The hardcoded lists in Tier 3 are sufficient for fallback.
     Adding `faker` as a fallback reintroduces the dependency we're avoiding, and the
     built-in lists cover the common cases. If a property has no hardcoded fallback,
     we generate `f"value_{i}"` placeholder strings — good enough for structural testing.

9. **Should we include the model in the `pip install`?**
   - **No.** PyPI has a hard 100MB package size limit. The smallest usable model
     (Qwen3 0.6B Q4) is ~500MB. Instead, `huggingface-hub` auto-downloads the model
     on first use with a progress bar, cached permanently at `~/.cache/huggingface/`.
     This is the same pattern used by `spacy`, `nltk`, `sentence-transformers`, etc.

---

## 17. Conclusion & Recommendation

**The hybrid approach (concept scheme extraction + local LLM generation) is the right
design for a library that will grow to support many shapes.**

**Key advantages over the original Faker approach:**
- **Zero per-shape code** for enumerated properties (concept schemes from ontology)
- **Zero per-property code** for literal values (LLM reads ontology metadata)
- **Truly generic** — add new shapes and get synthetic data automatically
- **Contextually realistic** — LLM understands "education data" context
- **Privacy-preserving** — local in-process LLM via `transformers`, no cloud API calls, no background service
- **Graceful degradation** — works without LLM via cache and fallback generators
- **Respectful to the end user** — `pip install ceds-jsonld[sdg]` is the only setup step;
  model auto-downloads on first use; nothing runs in the background when idle; no C
  compiler or build tools required

**The concept scheme handling alone justifies this approach.** 19,489 NamedIndividuals
across hundreds of concept schemes, all resolvable from the ontology we already load —
no need to hand-code any of those enumerations in a Faker provider.

**The `transformers` + `torch` runtime choice ensures a clean user experience.** Pre-built
wheels for all platforms (including Windows + CUDA), no C compiler required, no background
service. The model loads when the user's code runs and unloads when it finishes.
`llama-cpp-python` was rejected because it requires C/C++ build tools on Windows (see §5.0).

**Validated by end-to-end proof of concept (Feb 9, 2026).** The `bench_person_jsonld_dynamic.py`
script proved the full pipeline works: SHACL introspection → ontology metadata extraction
→ property classification → LLM prompt construction from ontology → structured JSON
generation → direct dict construction → valid Person JSON-LD document. The PoC:
- Generated a complete Person JSON-LD document matching the canonical example
- Used Qwen3 4B (full weights via transformers) at 14 tok/s on RTX 3090
- Resolved concept schemes via both strategies (sh:in and class-based)
- Loaded 235,672 triples from 3 ontology sources in 9 seconds
- Constructed the JSON-LD dict in 0.088ms
- All 557 project tests pass after SHACL property number corrections

See Section 1.1 for detailed PoC findings and performance numbers.

**Estimated effort:** 6-8 sessions for complete implementation.

**Next step:** Get approval on this revised design, then start with Phase 1 (concept
scheme resolver + fallback generators + CSV assembly) which works end-to-end without
any LLM dependency.

---

## Appendix A: End-to-End Proof of Concept — Person JSON-LD Dynamic Generator

> **Source:** `bench_person_jsonld_dynamic.py` (914 lines) — the validated PoC.
> This appendix captures the complete algorithm so it can be reproduced when building
> the production `SyntheticDataGenerator`.

### A.1 Prerequisites

```bash
pip install torch transformers huggingface-hub rdflib pyyaml orjson
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-4B')"
```

### A.2 Data Structures

```python
@dataclass
class PropertyMetadata:
    path_iri: str           # e.g. "http://ceds.ed.gov/terms#P000115"
    path_local: str         # e.g. "P000115"
    notation: str           # e.g. "FirstName" (from skos:notation)
    label: str              # e.g. "First Name" (from rdfs:label)
    description: str        # e.g. "The full legal first name..."
    range_type: str         # e.g. "string", "date", "token" or class local name
    range_iri: str          # Full IRI of schema:rangeIncludes
    max_length: int | None
    text_format: str        # e.g. "Alphanumeric", "YYYY-MM-DD"
    domain_label: str       # Parent class label, e.g. "Person Name"
    is_concept_scheme: bool # True if range is a CEDS class (not XSD)
    allowed_values: list[str]  # Resolved skos:notation values
```

### A.3 Algorithm — 7 Steps

**Step 1 — Load ontology resources:**
- Parse SHACL via `SHACLIntrospector(shacl_path)` → shape tree
- Load JSON-LD context → build IRI-to-name reverse lookup
- Load mapping YAML → property config, defaults, cardinality
- Load 3 ontology sources into single rdflib Graph:
  - `CEDS-Ontology.rdf` (235,570 triples)
  - `Common.ttl` (+60 triples)
  - `Person_Extension_Ontology.ttl` (+42 triples)
  - Total: 235,672 triples in ~9 seconds

**Step 2 — Classify properties:**
Walk SHACL shape tree. For each leaf property (skipping RecordStatus C200411 / DataCollection C200410):
- Extract metadata from ontology: `rdfs:label`, `dc:description`, `skos:notation`, `schema:rangeIncludes`, `ceds:maxLength`, `ceds:textFormat`
- If `allowed_values` (from `sh:in`) → resolve via `resolve_named_individuals()` → concept scheme
- Else if `schema:rangeIncludes` points to non-XSD class → resolve via `resolve_concept_scheme_members()` → concept scheme
- Else → literal (needs LLM)

**Step 3 — Load LLM:**
```python
from transformers import AutoModelForCausalLM, AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B", local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-4B", dtype=torch.bfloat16, device_map="cuda",
    attn_implementation="sdpa", local_files_only=True,
)
model.eval()
```

**Step 4 — Build LLM prompt from ontology metadata:**
For each literal property, include: context name, range type, max_length, description, text format, domain label. Prompt asks for one JSON object with those keys.

**Step 5 — Generate literal values:**
```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": ontology_driven_prompt},
]
text = tokenizer.apply_chat_template(messages, tokenize=False,
    add_generation_prompt=True, enable_thinking=False)
# generate with temperature=0.8, top_p=0.95, repetition_penalty=1.1
```
Parse JSON from output. Retry with lower temperature on parse failure.

**Step 6 — Assemble JSON-LD via direct dict construction:**
Walk SHACL shape tree again. For each sub-shape, build a dict with:
- `@type` from mapping YAML
- Literal fields as typed literals (`{"@value": ..., "@type": "xsd:..."}`)
- Concept scheme fields as random selections from resolved value pools
- RecordStatus/DataCollection injected from mapping defaults
- Cardinality (single dict vs list) from mapping YAML
- Build time: 0.088ms per record

**Step 7 — Validate:**
Walk SHACL shape tree one more time, verify:
- Top-level `@type`, `@context`, `@id` present
- Each sub-shape has correct `@type` and required fields
- Typed literals have `@value` and `@type`
- RecordStatus/DataCollection present where mapping expects them

### A.4 Concept Scheme Resolution Functions

**Strategy A — `sh:in` present (e.g., `hasPersonIdentificationSystem` with 21 values):**

```python
def resolve_named_individuals(ontology: Graph, allowed_iris: list[str]) -> list[str]:
    resolved = []
    for iri_str in allowed_iris:
        uri = URIRef(iri_str)
        notation = ontology.value(uri, SKOS.notation)
        if notation:
            resolved.append(str(notation))
        else:
            label = ontology.value(uri, RDFS.label)
            resolved.append(str(label) if label else iri_str.rsplit("#", 1)[-1])
    return resolved
```

**Strategy B — No `sh:in`, range is concept scheme class (e.g., `hasSex` → C000255):**

```python
def resolve_concept_scheme_members(ontology: Graph, class_iri: str) -> list[str]:
    members = []
    class_ref = URIRef(class_iri)
    for subj in ontology.subjects(RDF.type, class_ref):
        if (subj, RDF.type, OWL.NamedIndividual) in ontology:
            notation = ontology.value(subj, SKOS.notation)
            if notation:
                members.append(str(notation))
    return sorted(members)
```

### A.5 IRI-to-Name Reverse Lookup

```python
def build_iri_to_name(context: dict[str, str]) -> dict[str, str]:
    result = {}
    prefixes = {name: value for name, value in context.items()
                if not name.startswith("@") and isinstance(value, str)
                and (value.endswith("/") or value.endswith("#"))}
    for name, value in context.items():
        if name.startswith("@") or not isinstance(value, str):
            continue
        iri = value
        if ":" in iri and not iri.startswith("http"):
            prefix, local = iri.split(":", 1)
            if prefix in prefixes:
                iri = prefixes[prefix] + local
        result[iri] = name
    return result
```

> **Production note:** This duplicates `SHACLIntrospector._build_iri_to_name()`.
> Make that method public or extract to `ceds_jsonld.utils` to avoid duplication.

### A.6 Performance Results (RTX 3090, Qwen3-4B BF16, SDPA)

| Phase | Time |
|-------|------|
| Ontology load (3 sources, 235K triples) | 9.0s |
| Model load (8 GB, BF16, SDPA) | 7.3s |
| LLM generation (83 tokens) | 6.1s (14 tok/s) |
| Direct dict construction | 0.088ms |
| Peak VRAM | 7,890 MB |
| Total wall time | ~25s |

---

## Appendix B: Tier Benchmark Results

> **Sources:** `bench_concept_scheme.py`, `bench_ontology_metadata.py`,
> `bench_fallback_generators.py`, `run_all_benchmarks.py`

### B.1 Tier 1 — Concept Scheme Extraction (Zero-LLM)

**What it tests:** Can we resolve `sh:in` IRI lists to human-readable values
directly from the CEDS ontology without any LLM?

**Results:**

| Metric | Value |
|--------|-------|
| Ontology load time | ~8-9s |
| Ontology triples | ~235K |
| SHACL parse time | <0.1s |
| Total NamedIndividuals in ontology | ~19,489 |
| Properties with `sh:in` in Person shape | 3 (PersonIdentificationSystem, PersonIdentifierType, PersonIdentificationSystemType) |
| Resolution rate | 100% — all `sh:in` IRIs resolve to `skos:notation` |
| Per-property resolve time | <1ms |

**Algorithm:**
1. Parse SHACL → find properties with `PropertyInfo.allowed_values`
2. For each IRI in the list, query ontology for `skos:notation` (fallback: `rdfs:label`)
3. Return list of human-readable strings

**Assessment:** Trivially easy. No LLM needed for any enumerated property. The ontology
already has everything — 19,489 NamedIndividuals across hundreds of concept schemes.

### B.2 Tier 2 — Ontology Metadata Extraction (LLM Prompt Building)

**What it tests:** Is there enough metadata in the CEDS ontology to build quality
LLM prompts for literal value properties?

**Results (Person shape):**

| Metric | Value |
|--------|-------|
| Total shape properties | ~15 (across all sub-shapes) |
| Literal properties (need LLM) | ~6 |
| Concept scheme properties | ~4 |
| Metadata extraction time | <5ms |

**Metadata coverage for literal properties:**

| Field | Coverage |
|-------|----------|
| `rdfs:label` | 100% |
| `dc:description` | 100% |
| `ceds:maxLength` | ~83% (all string types) |
| `ceds:textFormat` | ~67% |
| `schema:rangeIncludes` | 100% |

**Sample extracted metadata for `FirstName` (P000115):**
- Label: "First Name"
- Description: "The full legal first name given to a person at birth, baptism, or through legal change."
- Range: `xsd:string`
- Max Length: 75
- Text Format: "Alphanumeric"
- Domain: "Person Name"

**Assessment:** Rich enough for excellent LLM prompts. The label + description + format
constraints give the LLM everything it needs to generate contextually appropriate values.

### B.3 Tier 3 — Fallback Generators (No LLM, No Cache)

**What it tests:** Pure-Python random generators as a safety net when no LLM is
available. Can they produce Pipeline-compatible data?

**Approach:** Hard-coded name lists (28 first names, 27 last names, 15 middle names),
random dates (YYYY-MM-DD, 1955-2020), random 9-digit IDs, concept scheme values from
known lists.

**Results:**

| Metric | Value |
|--------|-------|
| Generation rate | >150,000 rows/sec |
| Pipeline compatibility | PASS — all generated data flows through Pipeline end-to-end |
| Unique first names | 28 (from hard-coded list) |
| Unique last names | 27 (from hard-coded list) |
| SHACL validation | PASS (structural) |

**Scaling test:**

| Row Count | Time | Rate |
|-----------|------|------|
| 100 | <1ms | >100K rows/sec |
| 1,000 | ~5ms | ~200K rows/sec |
| 10,000 | ~50ms | ~200K rows/sec |
| 100,000 | ~500ms | ~200K rows/sec |

**Assessment:** Perfectly fast. Quality is acceptable for structural testing but limited
diversity (28 first names vs potentially thousands from LLM). This is the "works everywhere,
no dependencies" tier.

### B.4 Tier 2.5 — LLM Structured JSON Generation

**What it tests:** `llama-cpp-python` and Ollama generating structured JSON with
enforced schemas. (Note: production pivoted to `transformers` — see §5.0.)

**Results (from `bench_llm_generation.py`):**
- Tested with Qwen3 0.6B (GGUF Q4_K_M) via `llama-cpp-python`
- JSON schema adherence: enforced via `response_format` parameter
- 100% valid JSON when grammar-constrained output is used
- Value quality: realistic names, valid dates, proper ID formats
- Per-property generation: ~1-3s depending on value count requested

**Note:** This benchmark used `llama-cpp-python` which was later rejected for production
use (requires C build tools — see §5.0). The `transformers` runtime achieves similar
quality at ~14 tok/s on GPU. The structured output constraint approach differs:
`llama-cpp-python` uses grammar-enforced JSON schemas; `transformers` relies on
prompt engineering + JSON extraction from free-form output.

---

## Appendix C: GPU Benchmark Results — Qwen3-4B via Transformers

> **Source:** `quick_transformers_v2.py` — comprehensive GPU benchmark with
> quality metrics, diversity scoring, and batch comparison.

### C.1 Hardware & Software

| Component | Value |
|-----------|-------|
| GPU | NVIDIA RTX 3090 (24 GB VRAM) |
| CUDA | 12.4 |
| PyTorch | 2.6.0+cu124 |
| Transformers | 5.1.0 |
| Model | Qwen/Qwen3-4B (full weights, ~8 GB) |
| Dtype | BFloat16 |
| Attention | SDPA with flash backend |
| Thinking mode | Disabled (`enable_thinking=False`) |

### C.2 Single Record Generation (10 attempts)

| Metric | Value |
|--------|-------|
| Avg time/record | ~0.5-0.8s |
| Median | ~0.5s |
| P95 | ~1.0s |
| Tokens/sec | ~14 tok/s |
| JSON parse rate | ~90-100% |
| Schema valid rate | ~80-100% |
| Name diversity | High (unique per generation due to diversity hints) |

**Technique:** Random seed injection per call — each prompt includes a different
letter-range hint (e.g., "first name starting with A-D") and year hint (e.g.,
"born in 2007 or 2008") to prevent repetition across sequential calls.

### C.3 Batch Generation Comparison

| Batch Size | Time | Per-Record | Tokens/sec | Quality Score | Notes |
|-----------|------|-----------|-----------|--------------|-------|
| 5 | ~3-5s | ~0.6-1.0s | ~14 | 0.85-0.95 | High quality, good diversity |
| 10 | ~6-10s | ~0.6-1.0s | ~14 | 0.80-0.90 | Good, occasional ID duplication |
| 25 | ~15-25s | ~0.6-1.0s | ~14 | 0.75-0.85 | Some diversity loss at scale |
| 50 | ~30-50s | ~0.6-1.0s | ~14 | 0.70-0.80 | Noticeable repetition in longer batches |

**Quality score composition:** 30% schema validity + 20% ID uniqueness + 20% date
range compliance + 15% name diversity + 15% date diversity.

### C.4 Key Optimizations Applied

1. **BFloat16** — Better precision than FP16 on Ampere+ GPUs, same memory footprint
2. **SDPA attention** — PyTorch's built-in scaled dot product attention with flash backend
3. **`enable_thinking=False`** — Skips Qwen3's internal reasoning chain, ~2x faster
4. **`repetition_penalty=1.15`** — Discourages value reuse within a single generation
5. **Temperature 0.95 + top_p 0.95** — High diversity while maintaining format compliance
6. **Few-shot examples** — 2 example records in each prompt teach format + diversity
7. **Retry on parse failure** — One retry with lower temperature (0.5) on JSON parse failure

### C.5 Estimated Time for 100 Records

| Strategy | Estimated Time |
|----------|---------------|
| Single-record (100 sequential calls) | ~50-80s |
| Batch-of-25 (4 batches) | ~60-100s |
| Batch-of-50 (2 batches) | ~60-100s |

**Best strategy:** Single-record or small-batch (5-10), cached after first generation.
The per-record time is consistent regardless of approach; batch mode doesn't significantly
improve throughput because the token rate is GPU-bound at ~14 tok/s.

---

## Appendix D: Model Download Utility

For the production `[sdg]` extras, include a model download command or auto-download
on first use. The pattern from the PoC:

```python
from huggingface_hub import snapshot_download
path = snapshot_download(repo_id="Qwen/Qwen3-4B", repo_type="model")
# Cached at ~/.cache/huggingface/hub/ (~8 GB, one-time download)
```

This is the same pattern used by `spacy download`, `nltk.download()`, and
`sentence-transformers`. The model downloads once with a progress bar and is
permanently cached. No manual file management required.

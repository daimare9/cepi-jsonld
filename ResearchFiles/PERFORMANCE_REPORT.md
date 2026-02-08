# CSV-to-JSON-LD Performance Analysis Report

**Project:** CEDS JSON-LD Generator  
**Date:** February 6, 2026  
**Pipeline:** CSV → RDF (rdflib) → JSON-LD (PyLD frame/compact) → Output  
**Dataset:** 90 person records (CEDS Person shape), benchmarked up to 1M  

---

## Executive Summary

The existing pipeline processes CSV person records into compacted JSON-LD at **~7.2 ms/record**, projecting to **~2 hours for 1M records**. Profiling reveals that **73% of processing time is spent in PyLD** (framing + compaction), not in rdflib graph construction.

Three alternative approaches were benchmarked. The most impactful — direct dictionary construction — achieves **0.02 ms/record (161x speedup)**, processing **1M records in 33 seconds** end-to-end including JSON serialization and file I/O. Output fidelity has been verified field-by-field against the original pipeline.

---

## 1. Current Pipeline Architecture

```
CSV (pandas)
    │
    ▼
rdflib Graph          ← Create triples per person (BNodes, URIRefs, Literals)
    │
    ▼
g.serialize("json-ld") ← rdflib internal JSON-LD serializer (expanded form)
    │
    ▼
json.loads()           ← Parse string to Python dict
    │
    ▼
jsonld.frame()         ← PyLD: reshape flat nodes into nested tree
    │
    ▼
jsonld.compact()       ← PyLD: apply context, shorten IRIs to terms
    │
    ▼
JSON output            ← Compacted JSON-LD with human-readable keys
```

Each record creates a new `rdflib.Graph`, serializes it, and passes through two PyLD operations. The context is re-parsed on every call.

---

## 2. Bottleneck Profile

Measured across 90 records using `time.perf_counter()` at each phase boundary:

| Phase | Mean (ms) | Median (ms) | % of Total |
|:---|---:|---:|---:|
| 1. rdflib Graph creation | 1.063 | 0.780 | 12.8% |
| 2. rdflib JSON-LD serialize | 1.106 | 0.719 | 13.3% |
| 3. JSON parse (`json.loads`) | 0.037 | 0.028 | 0.4% |
| **4. PyLD frame** | **3.658** | **3.076** | **43.9%** |
| **5. PyLD compact** | **2.460** | **2.057** | **29.5%** |
| **TOTAL** | **8.325** | **7.446** | **100%** |

```
Phase Breakdown (mean per record):
──────────────────────────────────────────────────────
  Graph creation (rdflib)     ██████ 12.8%
  Serialize to JSON-LD        ██████ 13.3%
  JSON parse                   0.4%
  PyLD frame                  █████████████████████ 43.9%
  PyLD compact                ██████████████ 29.5%
```

**Conclusion:** PyLD frame + compact together consume **73.4%** of processing time. rdflib is responsible for only 26.1%. JSON parsing is negligible.

---

## 3. Root Cause: PyLD Performance Issues

Research into PyLD's GitHub repository reveals systemic, unresolved performance problems:

| Issue | Description | Status |
|:---|:---|:---|
| [#85](https://github.com/digitalbazaar/pyld/issues/85) | **No active context caching** — every `frame()` and `compact()` call re-parses the entire context from scratch | Open since 2018; slated for v3.0.0 |
| [#169](https://github.com/digitalbazaar/pyld/issues/169) | `_compare_rdf_triples` identified as CPU bottleneck | Open |
| [#179](https://github.com/digitalbazaar/pyld/issues/179) | Normalization algorithm performance issues | Open |
| [#104](https://github.com/digitalbazaar/pyld/issues/104) | `MAX_CONTEXT_URLS` limit and resolver overhead | Open |

The context caching issue (#85) is particularly relevant: our pipeline calls `frame()` and `compact()` 90 times with the identical context, and PyLD rebuilds its internal active context representation every single time.

---

## 4. Alternative Approaches Evaluated

### 4.1 Approach Comparison

| Approach | Mean (ms/rec) | Speedup | 1M Sequential | Dependencies |
|:---|---:|---:|:---|:---|
| **Original** (rdflib + PyLD) | 7.198 | 1.0x | ~2.0 hours | rdflib, PyLD, pandas |
| **rdflib auto_compact** | 1.743 | 4.1x | ~29 minutes | rdflib, pandas |
| **Direct Dict Construction** | 0.045 | **161x** | **~45 seconds** | pandas only |

### 4.2 Approach 1: Original Pipeline (Baseline)

The current implementation as described in Section 1. Creates a full rdflib `Graph` per person, serializes to expanded JSON-LD, then uses PyLD for framing and compaction.

- **Pros:** Full RDF graph available for SHACL validation; formally correct RDF semantics; context changes auto-propagate through PyLD compaction.
- **Cons:** ~73% of time wasted in PyLD; creates and discards a Graph object per record; no context caching in PyLD.

### 4.3 Approach 2: rdflib with `auto_compact`

rdflib's built-in JSON-LD serializer (merged from `rdflib-jsonld` into rdflib 6+) supports passing a context directly:

```python
result = g.serialize(format="json-ld", context=ctx["@context"], auto_compact=True)
```

This performs compaction internally using rdflib's own context engine, **bypassing PyLD entirely**.

- **Pros:** 4.1x speedup; still creates a proper RDF graph (SHACL-checkable); no PyLD dependency; uses `orjson` internally when available.
- **Cons:** Still materializes an rdflib Graph per record; output structure slightly different from PyLD framing (flat vs. nested — may need post-processing for deep nesting).

### 4.4 Approach 3: Direct Dictionary Construction

Since the mapping from CSV columns to compacted JSON-LD terms is **deterministic and known at development time**, we can construct the target output directly as Python dictionaries without any RDF intermediary:

```python
person = {
    "@context": "https://cepi-dev.state.mi.us/ontology/context-person.json",
    "@id": f"cepi:person/{person_id}",
    "@type": "Person",
    "hasPersonName": {
        "@type": "PersonName",
        "FirstName": row["FirstName"],
        "LastOrSurname": row["LastName"],
        ...
    },
    ...
}
```

- **Pros:** 161x speedup; zero external dependencies beyond pandas; output verified identical to original; trivially parallelizable (though unnecessary at this speed).
- **Cons:** No RDF graph for SHACL validation; schema changes require code updates (not just context file updates); the code embeds structural knowledge of the target JSON-LD shape.

---

## 5. End-to-End 1M Record Test (Direct Dict + orjson)

An actual 1,000,080-record test was executed (90-record dataset repeated 11,112 times):

| Phase | Time | Rate |
|:---|---:|:---|
| Dict construction | 19.7s | 0.020 ms/record |
| JSON serialization (orjson, indented) | 5.0s | 3,513 MB output |
| File write | 8.2s | Single sequential write |
| **Total end-to-end** | **33.0s** | **0.55 minutes** |

For comparison, the original pipeline projects to **~2 hours** for the same workload (sequential) or **~45 minutes** with 5-worker multiprocessing.

---

## 6. Parallelization Analysis

### 6.1 Original Pipeline (rdflib + PyLD)

Tested with `ProcessPoolExecutor` on 900 records (90 × 10 repeats), 22 CPU cores available:

| Config | ms/record | Speedup | 1M Projection |
|:---|---:|---:|:---|
| Sequential | 7.83 | 1.0x | 2.2 hours |
| 5 workers, batch=200 | 2.67 | 2.93x | 44.5 min |
| 10 workers, batch=100 | 2.71 | 2.88x | 45.2 min |
| 22 workers, batch=100 | 2.76 | 2.83x | 46.0 min |

**Finding:** Diminishing returns beyond 5 workers due to GIL contention in PyLD's pure-Python code. `ThreadPoolExecutor` showed **0.91x** (GIL-blocked, actually slower).

### 6.2 Direct Dict Construction

| Config | ms/record | Speedup |
|:---|---:|---:|
| Sequential | 0.012 | 1.0x |
| 4 workers, batch=500 | 0.109 | 0.1x (slower) |
| 8 workers, batch=500 | 0.155 | 0.1x (slower) |

**Finding:** At 0.012 ms/record, the per-record work is too cheap to amortize process startup and inter-process communication overhead. Multiprocessing is counterproductive here.

---

## 7. JSON Serialization Performance

The final JSON serialization step becomes significant at scale. Tested on 100K records:

| Library | Mode | Time | Factor |
|:---|:---|---:|---:|
| `json` (stdlib) | indent=2 | 1.94s | 1.0x |
| `json` (stdlib) | compact | 1.86s | 1.0x |
| **`orjson`** (C extension) | indent=2 | 0.48s | **4.1x** |
| **`orjson`** (C extension) | compact | 0.35s | **5.3x** |

`orjson` is a Rust-backed JSON library for Python with significantly better throughput. rdflib's own JSON-LD serializer already detects and uses it when available.

---

## 8. Alternative Python JSON-LD Libraries

| Library | Viability | Notes |
|:---|:---|:---|
| **PyLD** (digitalbazaar) | Current choice | Pure Python; known perf issues; most widely used |
| **rdflib built-in** | Viable replacement | auto_compact mode skips PyLD; good middle ground |
| **TRLD** | Not recommended | 13 GitHub stars; last updated 3 years ago; unproven |
| **rdflib-jsonld** | Archived | Merged into rdflib 6+; no separate install needed |
| Go/Rust/Java engines | Overkill | Would require subprocess/FFI bridge; unnecessary given direct-dict performance |

---

## 9. Output Fidelity Verification

The direct dict approach was verified against the original pipeline output (`person_compacted.json` vs `person_direct.json`):

| Check | Result |
|:---|:---|
| `@type` (all records) | ✅ Match |
| `@id` (all 90 records) | ✅ Match |
| `FirstName`, `LastOrSurname` | ✅ Match |
| `MiddleName`, `GenerationCodeOrSuffix` | ✅ Match (including omission when empty) |
| `Birthdate` (@type + @value) | ✅ Match |
| `hasSex` | ✅ Match |
| `hasRaceAndEthnicity` (single + array values) | ✅ Match |
| `hasPersonIdentification` (multi-node) | ✅ Match |
| `hasRecordStatus` (nested metadata) | ✅ Match |
| `hasDataCollection` (nested metadata) | ✅ Match |
| Array vs single-value handling | ✅ Match (1 item → object, 2+ items → array) |
| All 90 `@id` values sorted | ✅ Exact match |

---

## 10. Trade-off Matrix

| Dimension | Original (rdflib+PyLD) | rdflib auto_compact | Direct Dict |
|:---|:---|:---|:---|
| **Speed** | 7.2 ms/rec | 1.7 ms/rec | 0.02 ms/rec |
| **1M records** | ~2 hours | ~29 min | ~33 sec |
| **RDF graph available** | ✅ Yes | ✅ Yes | ❌ No |
| **SHACL validatable** | ✅ Yes | ✅ Yes | ❌ No |
| **Context auto-propagation** | ✅ Yes | ✅ Yes | ❌ Manual |
| **Nested output (framing)** | ✅ Full | ⚠️ Partial | ✅ Full |
| **External dependencies** | rdflib + PyLD | rdflib only | pandas only |
| **Code complexity** | Moderate | Low | Low |
| **Schema change effort** | Update context file | Update context file | Update code |

---

## 11. Recommendations

### For Maximum Throughput (1M+ records)

Use **Direct Dict Construction** with `orjson`. Expected: **~33 seconds for 1M records**. This is the recommended approach when the target schema is stable and SHACL validation is not required at generation time. See `benchmark_approaches.py` for the implementation.

### For Schema Safety with Good Performance

Use **rdflib `auto_compact`** — a 4x improvement over the current pipeline while retaining a proper RDF graph suitable for SHACL validation. No PyLD dependency. See Approach 2 in `benchmark_approaches.py`.

### For the Existing Pipeline (Incremental Improvement)

If the full PyLD frame+compact workflow must be retained:
1. **Cache the PyLD active context** between calls (monkey-patch or wait for PyLD v3.0.0)
2. Use `ProcessPoolExecutor` with 5 workers and batch sizes of 200 (~2.9x speedup)
3. Install `orjson` for faster final serialization

### For Large Output Files

At 3.5 GB for 1M records (indented JSON):
- Consider **NDJSON** (one JSON object per line) for streaming-friendly output
- Split into chunks (e.g., 100K records per file)
- Use compact JSON (no indent) to reduce to ~2.4 GB

---

## 12. Benchmark Scripts Reference

| Script | Purpose |
|:---|:---|
| `profile_bottleneck.py` | Phase-by-phase timing breakdown of original pipeline |
| `benchmark_approaches.py` | Side-by-side comparison of all 3 approaches with output verification |
| `benchmark_direct_scale.py` | Direct dict at 9K scale with multiprocessing tests |
| `benchmark_parallel_v2.py` | Original pipeline multiprocessing (5/10/22 workers) |
| `verify_output.py` | Deep field-by-field comparison + 100K scale test |

---

## Appendix A: Raw Benchmark Data

### A.1 Bottleneck Profile (90 records)

```
Phase                             Mean ms     Median   % of Total
------------------------------ ---------- ---------- ------------
1. Graph creation (rdflib)          1.063      0.780        12.8%
2. Serialize to JSON-LD             1.106      0.719        13.3%
3. JSON parse                       0.037      0.028         0.4%
4. PyLD frame                       3.658      3.076        43.9%
5. PyLD compact                     2.460      2.057        29.5%
TOTAL                               8.325      7.446       100.0%
```

### A.2 Multi-Approach Benchmark (90 records × 3 runs)

```
Approach                                Mean ms   Median  Speedup     1M est
-------------------------------------- -------- -------- -------- ----------
1. Direct Dict (no rdflib/PyLD)           0.045    0.043   161.0x     0.01 hr
2. rdflib + auto_compact                  1.743    1.329     4.1x     0.48 hr
3. Original (rdflib + PyLD)               7.198    6.125     1.0x     2.00 hr
```

### A.3 Actual 1M End-to-End (Direct Dict + orjson)

```
Build:  19.74s  (0.0197 ms/record)
JSON:    5.04s  (3,513 MB)
Write:   8.22s
TOTAL:  33.00s  (0.55 minutes)
```

---

*Report generated from benchmarks run on a 22-core Windows machine with Python 3.14, rdflib 7.x, PyLD 2.0.4, orjson 3.11.7.*

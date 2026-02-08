---
description: "Run performance benchmarks and compare against baseline numbers from PERFORMANCE_REPORT.md."
---
# Run Performance Benchmarks

## Baseline Reference

Read `ResearchFiles/PERFORMANCE_REPORT.md` for baseline numbers. Key baselines:

| Metric | Baseline | Source |
|--------|----------|--------|
| Direct dict: 1 record | ~X μs | PERFORMANCE_REPORT.md |
| Direct dict: 10K records | ~X ms | PERFORMANCE_REPORT.md |
| orjson serialization: 10K | ~X ms | PERFORMANCE_REPORT.md |
| rdflib+PyLD: 1 record | ~X ms | PERFORMANCE_REPORT.md (DO NOT USE in prod) |

## Procedure

### 1. Read Current Baselines
Read `ResearchFiles/PERFORMANCE_REPORT.md` to get the exact baseline numbers.

### 2. Run Benchmarks
Use `time.perf_counter()` for all measurements. Run each benchmark 5 times and take the median.

```python
import time
import statistics

def benchmark(func, *args, iterations=5):
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        func(*args)
        times.append(time.perf_counter() - t0)
    return statistics.median(times)
```

### 3. Standard Benchmarks

Run all of these:
1. **Single record build** — Build one JSON-LD document from a sample row
2. **10K records build** — Build 10,000 documents sequentially
3. **10K records + serialization** — Build + orjson.dumps for 10,000 documents
4. **SHACL validation (optional)** — pySHACL validate on one document
5. **End-to-end pipeline** — Read CSV → Map → Build → Serialize for N records

### 4. Report Format

```
## Benchmark Results

| Benchmark | Baseline | Current | Change |
|-----------|----------|---------|--------|
| 1 record build | X μs | Y μs | +/-Z% |
| 10K build | X ms | Y ms | +/-Z% |
| 10K build+serialize | X ms | Y ms | +/-Z% |

**Verdict:** ✅ No regression / ⚠️ Regression detected in [area]
```

### 5. Regression Handling

If any benchmark is >20% slower than baseline:
1. Identify what changed since the last benchmark
2. Profile the hot path
3. Fix or document the regression
4. Re-run benchmarks to confirm fix

### 6. Update Baselines

If benchmarks improve significantly (>20% faster), offer to update the baselines:
> "Performance improved by X%. Update baselines in PERFORMANCE_REPORT.md?"

Only update baselines with user approval.

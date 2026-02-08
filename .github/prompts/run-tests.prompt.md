---
description: "Run the test suite and report results. Includes coverage analysis and failure details."
---
# Run Tests

## Execution

Run the full test suite from the workspace root. **Run pytest directly — never pipe or
filter the output** (no `Select-String`, `grep`, `findstr`, etc.):

```powershell
pytest -v --tb=short --cov=src/ceds_jsonld --cov-report=term-missing
```

If the user specifies a subset:
- **Single file:** `pytest tests/{file}.py -v --tb=short`
- **Pattern match:** `pytest -k "{pattern}" -v --tb=short`
- **Performance only:** `pytest tests/benchmarks/ -v --tb=short`

**Do not re-run tests that already passed.** One run per change set. If tests pass, report
results and move on.

## Report Format

ALWAYS report results in this format:

```
## Test Results

**Status:** ✅ All passing / ❌ Failures detected
**Tests:** X passed, Y failed, Z skipped
**Coverage:** XX% overall

### Module Coverage
| Module | Coverage |
|--------|----------|
| builder | XX% |
| mapper | XX% |
| registry | XX% |

### Failures (if any)
1. `test_name` — Brief description of what failed and why
2. `test_name` — Brief description
```

## On Failure

If any test fails:
1. Read the failure output carefully
2. Identify the root cause
3. Fix the code (not the test, unless the test is wrong)
4. Re-run tests
5. Confirm all pass before reporting

## When to Run Tests

- **Once** after a logical set of related code changes (not after every micro-edit)
- Before marking a task as complete
- Before starting a new phase
- When the user says "run tests", "check tests", or "verify"
- **Never re-run tests that already passed.** If the suite passed, move on.

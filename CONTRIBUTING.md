# Contributing to ceds-jsonld

Thank you for your interest in contributing! This library helps education agencies convert data into CEDS-conformant JSON-LD — every contribution helps improve data interoperability across the education sector.

## Quick Links

- [Issues](https://github.com/daimare9/ceds-jsonld/issues) — Report bugs, request features
- [CHANGELOG.md](CHANGELOG.md) — What changed in each release
- [ROADMAP.md](ROADMAP.md) — Project plan and architecture decisions

---

## Getting Started

### Prerequisites

- Python 3.12+
- Git

### Setup

```bash
# Clone the repo
git clone https://github.com/daimare9/ceds-jsonld.git
cd ceds-jsonld

# Install in editable mode with all dev dependencies
pip install -e ".[dev,cli]"

# Verify everything works
pytest
```

### Project Structure

```
src/ceds_jsonld/       # Library source code
tests/                 # Test suite (pytest)
src/ceds_jsonld/ontologies/    # Shipped shape definitions (SHACL, context, mapping YAML)
docs/                  # Sphinx documentation
```

---

## Development Workflow

### 1. Create a branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` — new features
- `fix/` — bug fixes
- `docs/` — documentation changes
- `refactor/` — code refactoring (no behavior change)

### 2. Make your changes

Follow the coding standards below. Write tests for any new functionality.

### 3. Run the checks

```bash
# Tests
pytest

# Tests with coverage
pytest --cov=src/ceds_jsonld --cov-report=term-missing

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

All checks must pass before submitting a PR.

### 4. Submit a pull request

- Target the `main` branch
- Fill out the PR template
- Link any related issues
- Keep PRs focused — one feature or fix per PR

---

## Coding Standards

### Python Style

- **Line length:** 120 characters
- **Formatter/linter:** [Ruff](https://docs.astral.sh/ruff/)
- **Type hints:** Required on all public functions (`mypy --strict` compatible)
- **Docstrings:** Google style on all public classes and functions
- **Imports:** Use `from __future__ import annotations` in every module

### Testing

- Every code change must have a corresponding test
- Use real dependencies, not mocks (see below)
- Test files: `tests/test_<module>.py`
- Run: `pytest` (no grep, no filtering — read raw output)

### When to Mock

- **Do mock:** Live external services (Azure Cosmos DB endpoints, production APIs with auth tokens)
- **Don't mock:** Libraries you can install locally (openpyxl, httpx, sqlalchemy). Install them and test for real.
- If a dependency can't be installed, use `@pytest.mark.skip(reason="...")` — don't write a fake passing test.

### Performance

- The library is optimized for throughput. If your change is in the hot path (builder, mapper, serializer), include a benchmark comparison.
- Baseline: single record build < 0.05ms, 100K records < 10 seconds.

---

## Adding a New Shape

Shapes are self-contained folders. To add one:

1. Create `src/ceds_jsonld/ontologies/<shape_name>/`
2. Add these files:
   - `<ShapeName>_SHACL.ttl` — SHACL constraints
   - `<shape_name>_context.json` — JSON-LD context
   - `<shape_name>_mapping.yaml` — Field mapping config
   - `<shape_name>_sample.csv` — Sample data for testing
3. Add tests in `tests/test_<shape_name>.py`
4. The library auto-discovers shapes — no code changes needed

See `src/ceds_jsonld/ontologies/person/` for the reference implementation.

---

## Release Process

### Schedule

Releases follow a **monthly cadence** (first week of each month), with ad-hoc patch releases for critical bug fixes.

### Versioning

We use [Semantic Versioning](https://semver.org/):

| Change | Version Bump | Example |
|--------|-------------|---------|
| Breaking API change | MAJOR | 0.9.0 → 1.0.0 |
| New feature (backward-compatible) | MINOR | 0.9.0 → 0.10.0 |
| Bug fix | PATCH | 0.9.0 → 0.9.1 |

### How Releases Work

1. Maintainer updates `CHANGELOG.md` with the new version's changes
2. Version is bumped in `pyproject.toml` and `src/ceds_jsonld/__init__.py`
3. A Git tag is created: `git tag v0.9.1`
4. Push the tag: `git push origin v0.9.1`
5. GitHub Actions automatically builds and publishes to PyPI

---

## Reporting Issues

### Bug Reports

Include:
- Python version (`python --version`)
- Package version (`pip show ceds-jsonld`)
- Minimal reproduction code
- Expected vs actual behavior
- Full traceback

### Feature Requests

Include:
- Use case — what are you trying to accomplish?
- Proposed API — how would you like to call it?
- Alternatives considered

---

## Code of Conduct

Be respectful, constructive, and collaborative. We're all working toward better education data systems.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

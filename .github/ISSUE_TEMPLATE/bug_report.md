---
name: Bug Report
about: Report a bug in ceds-jsonld
title: "[BUG] "
labels: bug
assignees: ""
---

## Description

A clear description of the bug.

## Steps to Reproduce

```python
# Minimal code to reproduce the issue
from ceds_jsonld import Pipeline, ShapeRegistry, CSVAdapter

registry = ShapeRegistry()
registry.load_shape("person")
pipeline = Pipeline(source=CSVAdapter("data.csv"), shape="person", registry=registry)
# ...
```

## Expected Behavior

What you expected to happen.

## Actual Behavior

What actually happened. Include the full traceback if applicable.

```
Traceback (most recent call last):
  ...
```

## Environment

- **OS:** (e.g., Windows 11, Ubuntu 24.04)
- **Python version:** (e.g., 3.13.1)
- **ceds-jsonld version:** (e.g., 0.9.0)
- **Installed extras:** (e.g., `pip install ceds-jsonld[excel,fast]`)

## Additional Context

Any other context about the problem — sample data (sanitized), related issues, etc.

ADR-003: orjson for JSON Serialization
======================================

**Status:** Accepted

**Date:** 2025

Context
-------

The library serializes large numbers of JSON-LD documents. Standard library
``json`` is functional but slow for bulk workloads.

Decision
--------

**Use orjson (Rust-backed) for JSON serialization, with automatic fallback to
stdlib json.**

Rationale
---------

orjson is approximately **4–10x faster** than stdlib ``json`` for serialization.
At 1M records, this saves ~15 seconds of serialization time.

Implementation
--------------

The ``ceds_jsonld.serializer`` module provides a unified ``dumps()`` API:

.. code-block:: python

    try:
        import orjson
        def dumps(obj, *, pretty=False):
            option = orjson.OPT_INDENT_2 if pretty else 0
            return orjson.dumps(obj, option=option)
    except ImportError:
        import json
        def dumps(obj, *, pretty=False):
            indent = 2 if pretty else None
            return json.dumps(obj, indent=indent).encode()

Users install orjson via ``pip install ceds-jsonld[fast]``. The library works
correctly without it — just slower.

Tradeoffs
---------

**We gain:** Significant throughput improvement for large workloads.

**We accept:** An optional C-extension dependency. Mitigated by the automatic
fallback — the library never fails if orjson is absent.

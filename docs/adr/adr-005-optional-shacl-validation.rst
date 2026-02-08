ADR-005: Optional SHACL Validation
===================================

**Status:** Accepted

**Date:** 2025

Context
-------

SHACL validation proves that output documents conform to the shape constraints.
However, pySHACL validation is expensive because it requires:

1. Serializing the JSON-LD document to a string
2. Parsing it into an rdflib Graph
3. Running the SHACL validation engine

This costs approximately **50 ms per record** — for 1M records, that's ~14
hours.

Decision
--------

**SHACL validation is opt-in, not a required pipeline step.** Use lightweight
pre-build validation for 100% of records.

Implementation
--------------

Two validation tiers:

.. list-table::
   :header-rows: 1

   * - Tier
     - Speed
     - Coverage
     - When to use
   * - PreBuildValidator
     - ~0.01 ms/record
     - Required fields, datatypes, allowed values
     - Always — 100% of records
   * - SHACLValidator
     - ~50 ms/record
     - Full RDF conformance
     - Sample-based (1–5%) or post-load quality gate

Usage:

.. code-block:: python

    # Fast pre-build validation (always)
    result = pipeline.validate(mode="report")

    # Full SHACL validation on 5% sample
    result = pipeline.validate(mode="sample", shacl=True, sample_rate=0.05)

Three modes:

- **strict** — Raise on first error.
- **report** — Collect all issues, never raise.
- **sample** — Validate a random subset (configurable percentage).

Tradeoffs
---------

**We accept:** Not every record gets full RDF validation. A data error that
passes pre-build checks but fails SHACL is theoretically possible (though
unlikely if the pre-build rules are generated from the SHACL shape).

**We gain:** Viable throughput for production workloads. Pre-build validation
catches >99% of real-world issues at negligible cost.

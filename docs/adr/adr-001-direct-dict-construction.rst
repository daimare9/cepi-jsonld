ADR-001: Direct Dict Construction for JSON-LD
==============================================

**Status:** Accepted

**Date:** 2025

Context
-------

We need to generate JSON-LD documents from source data. Two approaches were
evaluated:

1. **rdflib + PyLD** — Build an RDF graph with rdflib, serialize to expanded
   JSON-LD, then compact using PyLD.
2. **Direct dict construction** — Build JSON-LD documents as plain Python
   dictionaries following the structure defined by the SHACL shape and context.

Decision
--------

**Use direct dict construction.** Build JSON-LD as plain Python dicts.

Rationale
---------

Benchmarking showed a **161x performance difference**:

.. list-table::
   :header-rows: 1

   * - Approach
     - Time per record
     - 1M records
   * - Direct dict
     - 0.02 ms
     - ~33 seconds
   * - rdflib + PyLD
     - 7.2 ms
     - ~2+ hours

The bottleneck in the rdflib+PyLD approach is PyLD's context compaction step,
which re-parses the context on every invocation (PyLD GitHub issue #85, open
since 2018; 73.4% of total time).

Tradeoffs
---------

**We lose:** An RDF graph as an intermediate representation. We cannot do
SPARQL queries or arbitrary graph operations on in-memory data.

**We gain:** Production-viable throughput for million-record datasets. The
target of processing 1M records in under 60 seconds is easily achievable.

**Mitigation:** SHACL validation (which requires a graph) is a separate,
optional step. Documents can be reconstituted into an rdflib Graph from their
JSON-LD representation when needed.

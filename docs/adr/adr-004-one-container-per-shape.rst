ADR-004: One Cosmos Container Per Shape
=======================================

**Status:** Accepted

**Date:** 2025

Context
-------

When loading JSON-LD documents into Azure Cosmos DB, we need to decide how
to organize containers.

Options considered:

1. **One container for all shapes** — All documents in a single container,
   partitioned by ``@type``.
2. **One container per shape** — Separate containers for Person, Organization,
   etc.

Decision
--------

**One container per shape.**

Rationale
---------

.. list-table::
   :header-rows: 1

   * - Concern
     - One container
     - One per shape
   * - Indexing policy
     - Must index union of all fields
     - Tuned per shape
   * - Partition key
     - One generic key
     - Shape-specific (e.g. ``orgId``)
   * - Throughput
     - Shared RU budget
     - Independent per shape
   * - Query patterns
     - Must cross-filter by type
     - Type-homogeneous
   * - TTL
     - One policy for all
     - Per-shape TTL rules
   * - Cost attribution
     - Mixed
     - Clean per-shape billing

Tradeoffs
---------

**We accept:** More containers to manage (one per shape). At typical scale
(5–20 shapes), this is manageable.

**We gain:** Simpler queries, optimized indexing, independent scaling, and
clean cost isolation.

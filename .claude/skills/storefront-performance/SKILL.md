---
name: storefront-performance
description: Optimize catalog/list/search/facets/autocomplete/cache/projection/query paths without breaking the v1.3 read-model architecture. Use for storefront performance work or query regressions.
effort: high
---
# Storefront performance
1. Use `ProductListingProjection` as the hot grid/API source; do not reintroduce OLTP join chains.
2. Keep Web and DRF on the same selector + DTO path.
3. Preserve GIN discrete facets and promoted typed range columns; EAV is not the hot filter index.
4. Measure first: query count, `EXPLAIN (ANALYZE, BUFFERS)`, `pg_stat_statements`, rows scanned, cache hit.
5. Preserve query-budget and N+1 tests.
6. Use compact keyset order `(sort_field, id)` and bounded crawl/query cost.
7. Projection writes converge by **compare-and-set on `projection_revision`**, not by source ordering (ADR-0014): dirty-identity trigger → observe the token **before** every source read's visibility point → rebuild the **whole candidate** from **authoritative** current state through `<domain>.public` batch selectors → commit only on **equality** of the observed token. A guard miss discards the candidate whole and rebuilds; an unchanged candidate writes nothing (no `UPDATE`, no token advance, no `updated_at`). Writes stay batched and coalesced, and the projection stays fully rebuildable from OLTP.
8. Do not introduce `source_version`, a monotonic source-version guard, a producer freshness token or a force-write path. No producer supplies a version; no domain learns it is projected.
9. The builder's source reads are **authoritative-read contract** reads — never a cache entry, a lagging replica or a snapshot opened before the observation. They are permanently excluded from any future read-replica admission.
10. Cache changes need cold-start behavior, single-flight, stale fallback, and bounded TTL/versioning. `updated_at` is display metadata; measure lag on the trigger pipeline.
11. Do not add OpenSearch, a read replica or PgBouncer: these are closed `INFRASTRUCTURE GATE`s needing a recorded evidence review, and the replica gate's contract is frozen by ADR-0016.

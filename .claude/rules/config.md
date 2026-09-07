---
paths:
  - "config/**/*.py"
  - "config/**/tests.py"
  - "config/**/tests/**/*.py"
---
# Composition root (`config/`) rules
- `config/` is the **only** composition root. It owns both **construction and injection**: it builds concrete adapters for `application/<a>/ports.py` ports and passes them into entry points (view/entry-point factory, `as_view()` binding, Celery handler registration, or another explicit startup binding).
- **No runtime package imports back into `config/`.** `interfaces/*` and `tasks/*` receive dependencies, never locate them — no container lookup, no settings-driven `import_module`, no module-level singleton reached from an entry point. This is what keeps the production source graph acyclic.
- `config/ → domains/<x>` is **PUBLIC ONLY**. The composition root may not import an owner-internal module, and specifically **may not import an owner-internal event contract** — a message schema is not a `public.py` export (ADR-0009 §6).
- `config/ → application/<a>` is the item-3 **SPECIAL** cell, frozen as:

  ```text
  config -> application/<a>:
      application/<a>/ports.py   ALLOWED
      application/<a>/public.py  ALLOWED
      every application internal module FORBIDDEN
  ```

  In particular `config` must **not** import an application module's use-case internals, selectors,
  application-owned ORM/models, internal DTO modules (not even for convenience), owner-internal
  event/message contract source, or internal services.
- `config` **constructs and binds ports** and **registers/injects public entry points**. It does not
  call, subclass, inspect or depend on application implementation internals — a binding that needs an
  internal symbol means the port or the public entry point is wrong, not that the cell should widen.
- The composition root passes actor values but owns **no** actor or error semantics.
- **Primary-only database configuration (ADR-0016):** one application database alias. No replica alias, no database router, no default read alias on a replica, and no sticky-primary/read-your-own-writes machinery for a replica that is not used. An HA standby, if operations runs one, receives no application reads.
- No infrastructure gate is opened here: no OpenSearch client, no PgBouncer assumption, no separate analytics/search/image service binding, no PostGIS.
- Bind only adapters for **enabled** workloads. Do not register a task route, queue, adapter or `INSTALLED_APPS` entry for a `LATER` module, and do not add settings-gated but unreachable code as a placeholder.
- Secrets come from the environment/secret store, never from a checked-in default; keep them out of logs, traces and fixtures.

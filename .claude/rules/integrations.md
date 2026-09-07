---
paths:
  - "integrations/**/*.py"
  - "integrations/**/tests.py"
  - "integrations/**/tests/**/*.py"
---
# Integration (vendor adapter) rules
- `integrations/*` is **pure Python anti-corruption adaptation**: it owns provider protocol, wire shape, auth, timeouts and error translation. It owns **no business state** — no Django model, no domain decision, no order/payment/inventory transition.
- Convert vendor payloads to/from explicit adapter DTOs; domain and application code never receives raw provider JSON.
- Outbound capabilities are **ports owned by `application/<a>/ports.py`** and implemented here. The adapter is imported only by the composition root in `config/` and by provider tests — never by `interfaces/*`, `tasks/*` or a domain.
- Split a provider package into an inbound `protocol` surface (importable by `interfaces/webhooks/<provider>`) and an `outbound` adapter surface (known only to the composition root).
- `integrations/*` depends on **neither** `core` public-contract primitive (the actor type, the structural error categories) — ADR-0006.
- Every outbound HTTP call has explicit connect/read/total timeouts, bounded retry with jittered backoff, a clamped `Retry-After`, and a per-vendor circuit breaker that fails fast without dropping a message.
- A provider wire schema and any internal registered message derived from it are **two separate contracts**; provider vocabulary never becomes internal event vocabulary.
- Provider amounts are compared **exactly** on amount and currency — no tolerance.
- An ambiguous provider outcome is resolved by the provider idempotency key or an application-owned status lookup/reconciliation, never by a blind transport retry.
- Keep provider credentials out of code, logs, traces, fixtures and snapshots.

---
paths:
  - "interfaces/**/*.py"
  - "interfaces/**/tests.py"
  - "interfaces/**/tests/**/*.py"
---
# Interface layer rules
- Interface code handles I/O, validation, authentication, serialization, rendering, status codes, and transport concerns.
- Do not place pricing, inventory, payment, or order business logic here.
- Use application/domain public contracts; do not fetch private ORM objects directly from request IDs.
- Web and DRF should consume the same application DTO/read path where they represent the same data.
- Webhooks only authenticate/validate and durably ingest; financial state transitions happen in workers/domain state machines. The inbound boundary writes no Outbox marker — the internal registered message is authored later by the owning application module.
- `interfaces/*` never imports `config/*`; entry points **receive** their dependencies from the composition root and never service-locate them. A webhook may import `integrations/<provider>/protocol` only — never an `outbound` adapter.
- Public locators are `PublicId` or purpose-bound signed tokens; internal bigint PKs never appear in URLs, payloads or external identifiers.

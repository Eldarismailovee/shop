---
name: integration-change
description: Implement or modify ERP/1C, maib, MIA, CRM, email/SMS, Chatwoot, or other external integrations, queues, Outbox/Inbox consumers, retries, terminal states, and reconciliation.
effort: high
---
# External integration change

## Adapter boundary
1. Provider code lives in `integrations/*` with provider DTOs at the anti-corruption boundary; it owns provider adaptation, **not business state**.
2. Domain/application code receives internal DTOs, never raw vendor JSON. A provider wire schema and any internal registered message derived from it are two separate contracts, and provider vocabulary never becomes internal event vocabulary.
3. The outbound capability is a port on `application/<a>/ports.py`; only `config/` binds the adapter. `tasks/*` never imports `integrations/*` or `config/*`.
4. Every outbound request has explicit connect/read/total timeouts, bounded retry with jittered backoff, and a per-vendor circuit breaker. Provider amounts are matched **exactly** on amount and currency.

## Message envelope
5. The envelope is exactly `event_id`, `event_type`, `schema_version`, `occurred_at`. Only a **registered** `(event_type, schema_version)` may be emitted; a published version is immutable, so an additive field is a **new version**, and consumers support **exact** versions (no "latest", no nearest-version coercion, no unknown-field tolerance).
6. The trace/causality extension is the closed four-field TCE: `trace_id`, `producer_span_id`, `request_id`, `causation_event_id`. No `correlation_id`, no metadata bag, no persisted baggage/`tracestate`, no ancestry path. Fields are captured at the durable Outbox INSERT inside the business transaction, are write-once, and are absence-tolerant.
7. **Do not name a generic message field `idempotency_key`.** Delivery identity is `event_id` (Inbox); a local command key is `IdempotencyKey (scope, key)`; an outbound provider retry key is the provider's own; an inbound webhook dedupes on the provider `external_event_id`. Keep the five separate.
8. `schema_version` is not a source version and not an ordering key; a routing change never bumps it.

## Failure semantics
9. Route by **logical failure domain**, assigned **per consumer declaration** (`core.payments`, `ext.payments`, `core.inventory`, `core.projection.incremental`, `core.projection.rebuild`, `core.maintenance`, `ext.erp`, `ext.email`, `ext.sms`, `ext.crm`). No general-purpose `default`/`external` queue; priority is not isolation. Provision only enabled workloads — `ext.sms` and `ext.crm` are defined but **not provisioned** at launch.
10. **Unknown `event_type` / unsupported `schema_version` / invalid contract → durable QUARANTINE + alert.** Never ignored, coerced, treated as latest, partially applied, retried forever or marked HANDLED. Quarantine **commits before** the transport disposes of the delivery.
11. **Understood work whose execution budget is exhausted → operational dead-letter for that consumer delivery.** This is a different state from quarantine, and neither is called "failed".
12. **PostgreSQL holds the canonical terminal state; the broker DLQ is transport only.** Order is validate → persist → COMMIT → only then dispose. A failed terminal write means the delivery is not disposed of.
13. The unit of failure, terminal identity and replay is a **consumer delivery**. Two consumers of one `event_id` are independent; one may succeed while another dead-letters; every terminal record names *which* consumer failed.
14. **Replay is consumer-delivery scoped**, explicit, authorised, audited and identity-preserving; it re-enters normal validation and idempotency with no force-apply path and never rebroadcasts to a sibling that already succeeded. A genuinely new business attempt is a new message with a new `event_id`.

## Payments and convergence
15. **Handler transaction rule (HT1), where it applies:** where a consumer has a correctness-relevant durable local effect whose atomicity matters, the Inbox claim/identity handling + that local effect + the resulting Outbox rows + the successful Inbox completion belong to **one local PostgreSQL transaction**. A consumer without such an effect is not required to invent one. In every case the Inbox is **never marked handled before the effect it protects is durable**, and **no provider or network I/O happens inside that transaction**. Provider-facing work follows HT4: persist local intent → `COMMIT` → perform the external call afterwards under the provider idempotency key, state machine and reconciliation. Inbox identity integrity and the per-consumer effect-idempotency declaration stand regardless of shape.
16. Reconciliation is the convergence source of truth; the webhook is an accelerator. An ambiguous provider outcome is resolved by the provider idempotency key or an application-owned status lookup — never by a blind transport retry.
17. Test timeout, duplicate delivery, same-`event_id`-different-content (an integrity violation), out-of-order, provider-down, retry exhaustion, quarantine, dead-letter and replay paths.

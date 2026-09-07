---
name: security-critical
description: Security checklist for auth, user-owned objects, checkout, payments, webhooks, coupons, Trade-In, uploads, PII, consent, secrets, or digital codes. Invoke automatically when these areas change.
effort: high
---
# Security-critical change
Before coding, load the relevant architecture section with `architecture-context`.
Check the applicable controls:
- actor-scoped ownership; no IDOR via public IDs;
- UUIDv7/PublicId or purpose-bound signed token externally;
- durable PostgreSQL idempotency, with the five mechanisms kept separate — local command `IdempotencyKey (scope, key)` + principal binding + semantic fingerprint; Inbox/`EventId` delivery identity; provider `external_event_id` webhook dedupe; outbound provider idempotency key; domain `UNIQUE`/state machine for the permanent effect;
- an idempotency key is never authorization and never an object-access token; a fingerprint is never authentication and carries no secret; expiry ends the replay promise, so permanent single-use rules need a domain constraint;
- provider I/O strictly post-commit, never inside the claim transaction;
- trace/TCE metadata never decides authorization, identity, money, idempotency, ordering or routing;
- exact Money amount/currency checks;
- atomic state transitions/constraints for stock, coupons, quotes, codes;
- webhook raw-body signature, constant-time compare, timestamp window, event uniqueness, state machine, reconciliation;
- CSRF/origin/session behavior at browser boundaries;
- trusted proxy/client-IP handling for rate limits;
- input/upload validation and decompression/file-type limits;
- PII/consent/anonymization and third-party data minimization;
- no secrets in code/logs/traces/test fixtures.
Add a regression/security test for the failure mode being prevented.

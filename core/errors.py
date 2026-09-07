"""The structural public-error categories (ADR-0006 §2, item 4 §13.1).

`core` owns exactly one root and five categories. They are **markers**: no messages, no
business vocabulary, no domain names, no vendor concepts, no HTTP status, no transport, no
persistence. Every *concrete* public error is defined and owned by its domain, in
`domains/<x>/errors.py`, and inherits both its domain root and exactly one category::

    class ExampleError(DomainError): ...                    # the domain's own root
    class WidgetNotFound(ExampleError, NotFoundError): ...  # concrete, domain-owned

That hybrid is deliberate. A shared hierarchy of *concrete* business errors in `core` was
rejected — it would give `core` business vocabulary against ADR-0004 §2. Per-domain
categories with no shared marker were rejected for a concrete failure: every transport
mapper would have to enumerate each domain's error names by hand, and a newly added domain
would silently map to a 500. Five stable things to branch on fixes that without moving
ownership.

**The taxonomy is closed by rule.** Adding a category requires an ADR; adding a business
error here is forbidden outright. `tests/architecture` asserts the exact membership.

Consumers are fixed by ADR-0006 §2 and are *not* "every package family": `domains` define
concrete errors over the categories, `application` maps a category to workflow behaviour,
`interfaces` to transport behaviour, `tasks` to retry/failure classification, and the
composition root may install a shared handler. `integrations/*` is excluded — an adapter
reports failure through the vendor-neutral contract of the port it implements, and never
raises or interprets a domain public error. Migrations are excluded too. That is L21, and
`tools/arch_check` reports it.

Two things that are deliberately *not* here:

* **Technical and unexpected faults** (item 4 §13.5). A database outage, an
  `OperationalError`, a `TypeError` or an unidentifiable `IntegrityError` is not a business
  error and is never wrapped into one merely to satisfy a façade. Masking a page-the-operator
  condition as a `Conflict` makes a category-driven retry policy do the wrong thing.
* **Message-contract integrity failures** (item 8 VL4, QU10). An unknown `event_type`, an
  unsupported `schema_version` or an invalid payload is quarantined and alerted — never
  surfaced as a domain error and never mapped to a business state transition. Those live in
  `core.events.errors` and derive from `Exception`, not from `DomainError`.
"""

from __future__ import annotations

__all__ = (
    "ConflictError",
    "DomainError",
    "InvalidStateError",
    "NotAllowedError",
    "NotFoundError",
    "ValidationError",
)


class DomainError(Exception):
    """The root every domain's public error hierarchy derives from.

    Callers may catch the root or a category; both are part of the contract (X4). The
    class carries no fields: a stable `code` and any frozen detail fields belong to the
    concrete, domain-owned error (X2), and no message or field ever carries a secret, a
    token or PII (X3).
    """


class NotFoundError(DomainError):
    """An object is intentionally not found, or not visible to this actor."""


class NotAllowedError(DomainError):
    """An authorization or policy denial.

    Whether a non-visible object raises this or `NotFoundError` is a per-domain decision
    recorded in that domain's contract, because the choice leaks existence information
    (item 4 Z8).
    """


class ConflictError(DomainError):
    """An expected business conflict, including an expected race on a *named* constraint.

    A domain may translate a database error into this category only when it can reliably
    identify the violated invariant, and only from inside its own savepoint (item 4 §13.4).
    "An `IntegrityError` happened somewhere in this block" is not identification.
    """


class InvalidStateError(DomainError):
    """An invalid or illegal state transition."""


class ValidationError(DomainError):
    """A business-rule or input validation failure."""

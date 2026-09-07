"""The ten frozen logical failure domains (item 9 §5, ADR-0010).

A **logical failure domain** is the unit of isolation: workloads share one only when one's
outage, latency, poison rate and retry storm may acceptably consume the other's capacity
(item 9 §4). It is one of three separated layers — registered message contract (item 8) /
logical failure domain (item 9) / physical broker queue (Phase 1) — and it is assigned **per
consumer declaration**, never per message version and never by the producer (RT3, RT12).

### Why all ten, when only eight are provisioned at launch

Item 14 §15's provisioning view enables eight: `ext.sms` and `ext.crm` are defined but not
provisioned, because SMS and CRM are `LATER`. That is not a reason to omit them from this set.
A frozen **definition** is never a launch **commitment** — the whole point of item 9 FD9a is
that `ext.crm`'s isolation rule binds *if and when* CRM is enabled — and item 9 A51/A56 check
that a routing assignment and a terminal record name a domain **that exists in the matrix**.
An enum member is a name that exists in the matrix. It provisions no queue, starts no worker,
stubs no adapter and enables no feature: absence of a `LATER` capability is the absence of a
call (item 14 NF1-NF12), and there is no call.

Deliberately absent, because no definition exists to name: any support/Chatwoot domain, any
analytics domain, any search domain (item 9 §5, item 13). Adding one is the matrix's own
recorded procedure, with an ADR where an isolation guarantee moves — not an edit here.

### What criticality does and does not mean

`Criticality` governs capacity, isolation and alerting **only** (item 9 §6). It never governs
durability, contract strength, or whether data may be lost, and it is never a source of
business inference: a `BEST_EFFORT` message is exactly as durable as a `CRITICAL` one. It is
recorded beside each domain because a terminal record's triage urgency follows from it, and
because reading it here is cheaper than reading it from an operations runbook that does not
exist yet.

Retry bounds, backoff seconds, jitter widths, circuit thresholds, worker counts, prefetch and
the physical queue topology are **not** here: item 9 defers every number to Phase 1 operations
and refuses to invent one, and `RB4` says so explicitly.
"""

from __future__ import annotations

from enum import Enum

__all__ = ("Criticality", "FailureDomain")


class Criticality(Enum):
    """Capacity, isolation and alerting class — never durability or contract strength."""

    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    BEST_EFFORT = "BEST_EFFORT"


class FailureDomain(Enum):
    """The closed set of logical failure domains item 9 §5 froze.

    The `core.` prefix asserts a checkable property: no work in a `core.*` domain performs
    provider I/O (item 9 QN3). That is why payments is split by **I/O nature** rather than by
    workflow step — `core.payments` converges local durable state and must keep converging
    through any provider outage, while `ext.payments` performs every provider-facing call
    under per-provider concurrency, rate-limit and circuit budgets. The queue boundary
    coincides with ADR-0007's transaction boundary, which is the point.
    """

    #: Local payment state convergence. No provider I/O, ever.
    CORE_PAYMENTS = "core.payments"
    #: Reservation expiry and local inventory convergence.
    CORE_INVENTORY = "core.inventory"
    #: Incremental storefront projection updates; freshness-shaped.
    CORE_PROJECTION_INCREMENTAL = "core.projection.incremental"
    #: Full and targeted projection rebuilds; throughput-shaped. Split from the incremental
    #: domain precisely so a rebuild backlog can never starve freshness (item 9 PJ2).
    CORE_PROJECTION_REBUILD = "core.projection.rebuild"
    #: Housekeeping: retention sweeps, purges, scheduled reconciliation.
    CORE_MAINTENANCE = "core.maintenance"

    #: Every provider-facing payment call, per provider budgets.
    EXT_PAYMENTS = "ext.payments"
    #: ERP/1C batch ingest and export. Bounded, set-based, resumable, idempotent.
    EXT_ERP = "ext.erp"
    #: Transactional email transport.
    EXT_EMAIL = "ext.email"
    #: Defined, **not provisioned** at launch: SMS is LATER (item 14 §5).
    EXT_SMS = "ext.sms"
    #: Defined, **not provisioned** at launch: CRM is LATER, which is item 14's resolution of
    #: item 9 FD9a. The isolation rule binds if and when CRM is enabled.
    EXT_CRM = "ext.crm"

    @property
    def criticality(self) -> Criticality:
        """The domain's capacity/isolation/alerting class (item 9 §6)."""
        return _CRITICALITY[self]

    @property
    def performs_provider_io(self) -> bool:
        """Whether work in this domain may make a provider call (item 9 QN3).

        A property of the **name**, checkable by reading it, which is exactly what the
        `core.`/`ext.` split was frozen to give.
        """
        return self.value.startswith("ext.")

    @property
    def terminal_namespace(self) -> str:
        """The per-domain terminal namespace (item 9 §21, TI2, A56).

        Item 9 forbids one global undifferentiated dead-letter bucket: a poison ERP batch must
        never sit in the same undiscriminated place as a payment reconciliation failure,
        because the two have different owners, different runbooks, different urgency and
        different replay authority. The namespace is derived from the domain rather than
        stored separately, so the two can never disagree.
        """
        return f"{self.value}.dlq"


_CRITICALITY: dict[FailureDomain, Criticality] = {
    FailureDomain.CORE_PAYMENTS: Criticality.CRITICAL,
    FailureDomain.EXT_PAYMENTS: Criticality.CRITICAL,
    FailureDomain.CORE_INVENTORY: Criticality.CRITICAL,
    FailureDomain.CORE_PROJECTION_INCREMENTAL: Criticality.IMPORTANT,
    FailureDomain.CORE_PROJECTION_REBUILD: Criticality.IMPORTANT,
    FailureDomain.EXT_ERP: Criticality.IMPORTANT,
    FailureDomain.CORE_MAINTENANCE: Criticality.BEST_EFFORT,
    FailureDomain.EXT_EMAIL: Criticality.BEST_EFFORT,
    FailureDomain.EXT_SMS: Criticality.BEST_EFFORT,
    FailureDomain.EXT_CRM: Criticality.BEST_EFFORT,
}

"""Emission-path failures (item 8 §20, item 15 §15 clause 5).

These are **not** `core.errors.DomainError`s, for the same reason
`core.events.errors.MessageContractError` is not: an emission defect is a contract or
platform-integrity failure, never a business outcome, and must not be catchable by a handler's
`except DomainError` and quietly turned into one.

They are also not `MessageContractError`s. That hierarchy describes a *message* whose contract
cannot be honoured — unknown type, unsupported version, invalid payload — whose outcome is
durable quarantine plus an alert. These describe a *caller* using the emission mechanism
incorrectly, which is a programmer defect (item 9's TF-D) and is fixed in code, not triaged in
a runbook.
"""

from __future__ import annotations

__all__ = ("EmissionError", "EmissionOutsideTransaction")


class EmissionError(Exception):
    """The root of Outbox emission defects."""


class EmissionOutsideTransaction(EmissionError):
    """`emit()` was called outside a transaction.

    Item 8's handler transaction rule and ADR-0007 require the durable message to become
    durable with the fact it describes. In autocommit the row would commit on its own, so a
    business transaction that later rolled back would leave a message announcing a fact that
    never happened — the one failure an Outbox exists to make impossible.
    """

"""The physical bounds of a durable message record (item 8 PD8, item 9, item 10 RQ6).

Item 8 requires a payload to be **bounded** and fixes no number; item 10 bounds `request_id`
and fixes no number. The numbers are chosen here, in one place, so that "bounded" is a
physical guarantee of the schema rather than an intention in prose — and so that the Outbox
row, the Inbox delivery and the terminal record cannot drift apart, since all three store the
same envelope.

Every one of them is also a database constraint (`core/outbox/models.py`,
`core/inbox/models.py`), because a Python-side bound is not a bound against `bulk_create`,
raw SQL or a concurrent writer.

Widening one of these is a migration and a recorded decision, not an edit.
"""

from __future__ import annotations

__all__ = (
    "FINGERPRINT_HEX_LENGTH",
    "MAX_CONSUMER_LENGTH",
    "MAX_EVENT_TYPE_LENGTH",
    "MAX_PAYLOAD_BYTES",
    "MAX_REASON_LENGTH",
    "MAX_RELAY_WORKER_LENGTH",
    "MAX_REQUEST_ID_LENGTH",
    "SPAN_ID_HEX_LENGTH",
    "TRACE_ID_HEX_LENGTH",
)

#: An owner-qualified dotted name such as `<owner>.<fact>` (item 8 NM1-NM3). Generous for a
#: dotted platform-owned name; it is never user input, so it never needs to be long.
MAX_EVENT_TYPE_LENGTH = 128

#: A registered consumer's dotted module name. The unit of failure, terminal identity and
#: replay is the **consumer delivery** (item 9 §22.3), so this column is never optional and
#: never a domain name: a failure domain shared by several consumers cannot identify one.
MAX_CONSUMER_LENGTH = 128

#: Item 8 PD8: a payload is bounded. 256 KiB is far above any legitimate semantic message and
#: far below a row dump; a producer that needs more is describing a file, not a fact, and the
#: message should carry a reference instead (item 8's snapshot-vs-reference rule).
MAX_PAYLOAD_BYTES = 262_144

#: SHA-256 over the payload's canonical bytes, rendered as lowercase hex. Fixed width, and
#: the alphabet is checkable in SQL.
FINGERPRINT_HEX_LENGTH = 64

#: W3C Trace Context identifier widths, as hex text (item 10 TR2, SP4).
TRACE_ID_HEX_LENGTH = 32
SPAN_ID_HEX_LENGTH = 16

#: Item 10 RQ6: a bounded-length opaque token. Kept identical to the value
#: `core/events/envelope.py` validates, so the column and the type agree by construction.
MAX_REQUEST_ID_LENGTH = 128

#: The relay worker's identity on a claimed lease. Operational metadata, never message data.
MAX_RELAY_WORKER_LENGTH = 128

#: A terminal record's machine-readable reason token (item 9 DL4). Bounded because a terminal
#: record is a triage handle, not a log line: the diagnosis lives in the alert and the runbook.
MAX_REASON_LENGTH = 512

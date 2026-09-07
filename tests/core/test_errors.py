"""The structural public-error categories (ADR-0006 §2, item 4 §13).

Two properties carry the whole design: the taxonomy is **closed** at one root plus five
categories, and it is **structural** — no messages, no business vocabulary, no HTTP, no
transport, no persistence, no vendor.
"""

from __future__ import annotations

import ast
import inspect

import pytest

import core.errors as errors
from core.errors import (
    ConflictError,
    DomainError,
    InvalidStateError,
    NotAllowedError,
    NotFoundError,
    ValidationError,
)
from tests.conftest import REPO_ROOT

CATEGORIES = (
    NotFoundError,
    NotAllowedError,
    ConflictError,
    InvalidStateError,
    ValidationError,
)


def test_the_taxonomy_is_closed_at_one_root_plus_five_categories() -> None:
    """Closed by rule: adding a category requires an ADR; adding a business error is
    forbidden outright. This asserts the membership, so growth cannot happen quietly."""
    public = {
        name
        for name, value in vars(errors).items()
        if not name.startswith("_") and inspect.isclass(value)
    }
    assert public == {"DomainError", *(category.__name__ for category in CATEGORIES)}
    assert set(errors.__all__) == public


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_category_derives_from_the_one_root(category: type) -> None:
    """X4: a caller may catch the domain root or the category; both are the contract."""
    assert issubclass(category, DomainError)
    assert category.__mro__ == (category, DomainError, Exception, BaseException, object)


def test_the_root_derives_from_nothing_but_exception() -> None:
    """No persistence, transport or vendor exception is anywhere in the ancestry."""
    assert DomainError.__mro__ == (DomainError, Exception, BaseException, object)


def test_a_domain_error_composes_a_domain_root_with_exactly_one_category() -> None:
    """Item 4 §13.1's shape, which A23 will check once a domain publishes one."""

    class ExampleError(DomainError):
        """Stands in for a domain's own root; no such domain exists yet."""

    class WidgetNotFound(ExampleError, NotFoundError):
        """A concrete, domain-owned error."""

    raised = WidgetNotFound()
    assert isinstance(raised, ExampleError)
    assert isinstance(raised, NotFoundError)
    assert isinstance(raised, DomainError)
    assert sum(isinstance(raised, category) for category in CATEGORIES) == 1


@pytest.mark.parametrize("category", (DomainError, *CATEGORIES))
def test_a_category_is_a_marker_and_carries_no_payload(category: type) -> None:
    """The markers hold no `code`, message or detail field: a stable `code` and any frozen
    detail fields belong to the concrete, domain-owned error (X2)."""
    assert {name for name in vars(category) if not name.startswith("__")} == set()
    assert "__init__" not in vars(category)
    assert category().args == ()


def test_no_transport_vendor_or_persistence_vocabulary_reaches_the_taxonomy() -> None:
    """§13.6: a public error that carries an HTTP status is a transport concept inside a
    domain and is forbidden. `core.errors` imports nothing at all."""
    for category in (DomainError, *CATEGORIES):
        exposed = {name for name in dir(category) if not name.startswith("_")}
        assert not exposed & {
            "status_code",
            "http_status",
            "default_detail",
            "default_code",
            "params",
            "message_dict",
        }

    tree = ast.parse((REPO_ROOT / "core" / "errors.py").read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom)]
    modules = {getattr(n, "module", None) or "" for n in imports} | {
        alias.name for n in imports if isinstance(n, ast.Import) for alias in n.names
    }
    assert modules <= {"__future__"}


def test_a_message_contract_failure_is_not_a_business_error() -> None:
    """VL4, QU10: an unknown type, an unsupported version or an invalid payload is a
    contract-integrity failure that is quarantined and alerted — never catchable as a
    domain error, and never mapped to a business state transition."""
    from core.events.errors import (
        MessageContractError,
        UnknownEventType,
        UnsupportedSchemaVersion,
    )

    for failure in (MessageContractError, UnknownEventType, UnsupportedSchemaVersion):
        assert not issubclass(failure, DomainError)
        assert issubclass(failure, Exception)

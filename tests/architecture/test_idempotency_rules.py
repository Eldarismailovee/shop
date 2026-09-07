"""A129-A138 — the command-idempotency static rules (ADR-0015, item 15 §13.1).

Each rule is exercised against a throwaway tree that deliberately breaks it, and against
one that does not, so a rule that silently stops firing fails here rather than passing
forever. The real `core/idempotency/**` is checked by the harness run in
`test_repository_layout.py`; these cases prove the rules have teeth.
"""

from __future__ import annotations

_MODEL_HEAD = "from django.db import models\n\n\nclass IdempotencyKey(models.Model):\n"

_GOOD_MODEL = (
    _MODEL_HEAD + "    scope = models.CharField(max_length=128)\n"
    "    key = models.CharField(max_length=255)\n\n"
    "    class Meta:\n"
    "        constraints = [\n"
    "            models.UniqueConstraint(\n"
    "                fields=('scope', 'key'), name='core_idem_scope_key_uniq'\n"
    "            ),\n"
    "        ]\n"
)

_GOOD_CLAIM = (
    "from core.idempotency.scopes import COMMAND_SCOPES\n"
    "from core.idempotency.outcomes import SemanticResult\n\n"
    "_CLAIM_PATH_FIELDS = ('scope', 'key', 'result_kind')\n\n\n"
    "def claim_or_resolve(*, scope, key):\n"
    "    command_scope = COMMAND_SCOPES.resolve(scope)\n"
    "    return SemanticResult(kind='created', public_id=None, detail_json=None)\n"
)


# ---------------------------------------------------------------------------
# A129 — the claim is a PostgreSQL write
# ---------------------------------------------------------------------------


def test_a129_rejects_a_redis_backed_claim(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"core/idempotency/claim.py": "import redis\n"})
    assert "A129" in found


def test_a129_rejects_an_in_process_lock(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"core/idempotency/claim.py": "import threading\n"})
    assert "A129" in found


def test_a129_rejects_a_cache_backed_short_circuit(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path, {"core/idempotency/claim.py": "from django.core.cache import cache\n"}
    )
    assert "A129" in found


def test_a129_rejects_an_advisory_lock_as_the_claim(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/claim.py": (
                "def claim():\n    return 'SELECT pg_advisory_xact_lock(1)'\n"
            )
        },
    )
    assert "A129" in found


def test_a129_leaves_an_ordinary_database_claim_alone(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/claim.py": (
                "from django.db import IntegrityError, transaction\n" + _GOOD_CLAIM
            ),
            "core/idempotency/models.py": _GOOD_MODEL,
        },
    )
    assert "A129" not in found


# ---------------------------------------------------------------------------
# A130 — UNIQUE (scope, key) is a database constraint
# ---------------------------------------------------------------------------


def test_a130_rejects_a_model_without_the_unique_constraint(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"core/idempotency/models.py": _MODEL_HEAD + "    scope = models.CharField()\n"},
    )
    assert "A130" in found


def test_a130_rejects_a_python_side_uniqueness_check(tmp_path, arch_rules):
    """`Model.clean()` does not run on bulk_create, raw SQL, or a concurrent writer."""
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/models.py": (
                _MODEL_HEAD + "    scope = models.CharField()\n\n"
                "    def clean(self):\n"
                "        if IdempotencyKey.objects.filter(scope=self.scope).exists():\n"
                "            raise ValueError('duplicate')\n"
            )
        },
    )
    assert "A130" in found


def test_a130_accepts_the_declared_constraint(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"core/idempotency/models.py": _GOOD_MODEL})
    assert "A130" not in found


# ---------------------------------------------------------------------------
# A131 — the claim commits with the effect it protects
# ---------------------------------------------------------------------------


def test_a131_rejects_a_durable_claim_transaction(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/claim.py": (
                "from django.db import transaction\n\n\n"
                "def claim():\n"
                "    with transaction.atomic(durable=True):\n        pass\n"
            )
        },
    )
    assert "A131" in found


def test_a131_rejects_an_on_commit_claim(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/claim.py": (
                "from django.db import transaction\n\n\n"
                "def claim():\n    transaction.on_commit(lambda: None)\n"
            )
        },
    )
    assert "A131" in found


def test_a131_rejects_an_independent_commit(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/claim.py": (
                "from django.db import transaction\n\n\ndef claim():\n    transaction.commit()\n"
            )
        },
    )
    assert "A131" in found


def test_a131_allows_a_savepoint(tmp_path, arch_rules):
    """Nesting is a savepoint implementation detail of one semantic command (item 4 §12)."""
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/claim.py": (
                "from django.db import transaction\n\n\n"
                "def claim():\n    with transaction.atomic():\n        pass\n"
            )
        },
    )
    assert "A131" not in found


# ---------------------------------------------------------------------------
# A132 — no durable processing/failed state
# ---------------------------------------------------------------------------


def test_a132_rejects_a_state_column(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"core/idempotency/models.py": _GOOD_MODEL + "    state = models.CharField()\n"},
    )
    assert "A132" in found


def test_a132_rejects_a_status_column_under_another_name(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"core/idempotency/models.py": _GOOD_MODEL + "    status = models.CharField()\n"},
    )
    assert "A132" in found


def test_a132_rejects_a_retry_counter(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"core/idempotency/models.py": _GOOD_MODEL + "    attempts = models.IntegerField()\n"},
    )
    assert "A132" in found


def test_a132_leaves_the_stateless_model_alone(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"core/idempotency/models.py": _GOOD_MODEL})
    assert "A132" not in found


# ---------------------------------------------------------------------------
# A133 — scope comes from the platform-owned set
# ---------------------------------------------------------------------------


def test_a133_rejects_a_claim_path_that_never_resolves_a_scope(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"core/idempotency/claim.py": "def claim_or_resolve(*, scope, key):\n    return scope\n"},
    )
    assert "A133" in found


def test_a133_accepts_a_registry_resolved_scope(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"core/idempotency/claim.py": _GOOD_CLAIM})
    assert "A133" not in found


# ---------------------------------------------------------------------------
# A134 / A135 — no credential, session or transport material
# ---------------------------------------------------------------------------


def test_a134_rejects_a_csrf_token_in_fingerprint_material(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/fingerprint.py": (
                "def fingerprint(*, csrf_token, body):\n    return body\n"
            )
        },
    )
    assert "A134" in found


def test_a134_rejects_a_session_input(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/fingerprint.py": (
                "def fingerprint(session_key):\n    return session_key\n"
            )
        },
    )
    assert "A134" in found


def test_a135_rejects_a_stored_response_header(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/models.py": (
                _GOOD_MODEL + "    response_headers = models.JSONField()\n"
            )
        },
    )
    assert "A135" in found


def test_a135_rejects_a_stored_cookie(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"core/idempotency/models.py": _GOOD_MODEL + "    cookies = models.JSONField()\n"},
    )
    assert "A135" in found


def test_the_vocabulary_rule_matches_words_not_substrings(tmp_path, arch_rules):
    """`is_fingerprint` and `token_count` must not read the same way."""
    found = arch_rules(
        tmp_path,
        {"core/idempotency/fingerprint.py": "def is_fingerprint(value):\n    return True\n"},
    )
    assert "A134" not in found


# ---------------------------------------------------------------------------
# A136 — the heavy column is off the claim path
# ---------------------------------------------------------------------------


def test_a136_rejects_selecting_the_heavy_column_while_claiming(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/claim.py": (
                "from core.idempotency.scopes import COMMAND_SCOPES\n\n"
                "_CLAIM_PATH_FIELDS = ('scope', 'key', 'result_detail')\n\n\n"
                "def claim_or_resolve(scope):\n    return COMMAND_SCOPES.resolve(scope)\n"
            )
        },
    )
    assert "A136" in found


def test_a136_rejects_an_unshaped_claim_read(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/claim.py": (
                "from core.idempotency.scopes import COMMAND_SCOPES\n\n\n"
                "def claim_or_resolve(scope):\n    return COMMAND_SCOPES.resolve(scope)\n"
            )
        },
    )
    assert "A136" in found


def test_a136_accepts_a_claim_path_without_the_heavy_column(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"core/idempotency/claim.py": _GOOD_CLAIM})
    assert "A136" not in found


# ---------------------------------------------------------------------------
# A137 — message identity is not a command key
# ---------------------------------------------------------------------------


def test_a137_rejects_an_event_id_in_the_command_mechanism(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"core/idempotency/claim.py": "from core.events.identity import EventId\n"},
    )
    assert "A137" in found


def test_a137_leaves_the_separate_mechanisms_separate(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"core/idempotency/claim.py": _GOOD_CLAIM})
    assert "A137" not in found


# ---------------------------------------------------------------------------
# A138 — no replay path bypasses the ownership check
# ---------------------------------------------------------------------------


def test_a138_rejects_a_second_result_construction_site(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/claim.py": (
                "from core.idempotency.scopes import COMMAND_SCOPES\n"
                "from core.idempotency.outcomes import SemanticResult\n\n"
                "_CLAIM_PATH_FIELDS = ('scope', 'key')\n\n\n"
                "def replay(row):\n"
                "    return SemanticResult(kind='a', public_id=None, detail_json=None)\n\n\n"
                "def peek(row):\n"
                "    COMMAND_SCOPES.resolve('x.y')\n"
                "    return SemanticResult(kind='b', public_id=None, detail_json=None)\n"
            )
        },
    )
    assert "A138" in found


def test_a138_accepts_a_single_result_construction_site(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"core/idempotency/claim.py": _GOOD_CLAIM})
    assert "A138" not in found

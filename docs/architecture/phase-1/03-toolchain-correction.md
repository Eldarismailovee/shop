# Phase 1 — Slice 3: toolchain correction, type checking, and version control

- **Status:** DONE
- **Date:** 2026-09-07
- **Phase:** 1 — first production code
- **ADRs:** **none required.** This slice removes two dependencies that no slice had recorded,
  adopts a type checker that [Slice 1](01-repository-bootstrap.md) §11 and
  [Slice 2](02-core-primitives.md) §10 both left open, and fills Slice 1 §11's "the repository is
  not under version control" deferral. No frozen artifact or accepted ADR was edited, and no frozen
  rule was changed.
- **Implements:** item 14 §5 / NF-series (launch cut); item 15 §15 clause 1 (reproducible build).
- **Builds on:** Slices 1 and 2, both accepted and unchanged.

---

## 1. Why this slice exists

An audit of `pyproject.toml` found four dependencies that no Phase-1 artifact records, and a type
checker configuration that could not run at all. Two of the four contradicted the launch cut
outright. Nothing here is a new architectural decision; it is the toolchain catching up with what
Slices 1 and 2 already froze.

---

## 2. `celery` and `redis` removed

Both were declared in `[project] dependencies`. Neither was imported anywhere in `core`, `domains`,
`application`, `interfaces`, `integrations`, `tasks`, `config`, `tests` or `tools`; `tasks/` held
only an empty `__init__.py`, there was no Celery app, no broker setting and no `CACHES` entry.

They also contradicted the record:

| Artifact | Statement |
|---|---|
| Slice 1 §2 | "**Not added:** DRF, Celery, a cache client, a type checker, an email/SMS/CRM/search/pooler package." |
| Slice 1 §11 | "Celery app and routing … the slices that need them; queues follow item 14 §15's provisioning view" |
| Slice 2 §1 | "Deliberately **not** created: … Celery; DRF; a cache client" |

Item 14's launch cut forbids a queue provisioned for a workload that is not enabled, and forbids
behaviour that changes on package presence. A broker client on the dependency list with no
configuration and no consumer is exactly the provisioning the cut rejects — the absence of a
capability is expressed by the absence of a call, which here means the absence of the dependency
too.

**Both were removed.** `uv lock` dropped 14 transitive packages with them (44 → 30). They return
with the slice that configures a broker or a cache, under item 14 §15's provisioning view.

A comment on `[project] dependencies` now records the rule, so the next addition is a deliberate
act rather than a convenience.

## 3. `mypy` and `django-stubs` kept, fixed, and recorded

Slice 1 §11 and Slice 2 §10 both list "a type checker" as *not required by that slice* — a
deferral, not a prohibition. This slice fills it: `Y1`–`Y3` are typing obligations, and the `core`
primitives are now concrete enough for a checker to be worth its keep.

Two corrections were needed.

**The plugin could not start.** `[tool.django-stubs] django_settings_module` pointed at
`config.settings`, which raises `ImproperlyConfigured` when a secret is absent — deliberately, so
that no secret has a checked-in default. The django-stubs plugin imports the settings module while
constructing its Django context, so *every* mypy run ended in `INTERNAL ERROR`. It now points at
`tests.settings`, which seeds throwaway values and re-exports `config.settings` unchanged — the
same module `pytest` has always used. The launch settings keep their no-default rule untouched.

**Strictness is calibrated, not blanket.** Production packages keep full `strict`, and were already
clean under it. Two narrow overrides apply to the harness and the suite:

- `tests.*`, `tools.*` — `disallow_untyped_defs`, `disallow_incomplete_defs` and
  `disallow_untyped_calls` off: a table-driven architecture case reads better without a return
  annotation on every entry.
- `tests.*` — `strict_equality` and `warn_unused_ignores` off. A negative test deliberately does
  what the type system forbids in order to prove the *runtime* rejects it: comparing a `PublicId`
  to an `EventId` to assert they never match (C127), or assigning an unknown attribute to assert
  `__slots__` raises. Real error classes — `arg-type`, `attr-defined`, `return-value` — stay on.

Where the checker found something genuine it was fixed rather than suppressed:

| Site | Fix |
|---|---|
| `tools/arch_check/rules.py` `_assigns_all` | returns `TypeGuard[Assign \| AnnAssign \| AugAssign]`; the bare `ast.AST` that `ast.walk` yields declares no `lineno` |
| `tools/arch_check/rules.py` A3 class-base loop | loop variable renamed `base_expr`; it had shadowed a `str` bound by an earlier `ImportFrom` loop in the same function |
| `tools/arch_check/rules.py` `_a5_units` | `list[ast.stmt]`, matching what it actually collects |
| `tools/arch_check/rules.py` A5 owner walk | narrowed to `ast.Name \| ast.Attribute`, the only nodes `_chain` answers for |
| `tests/core/test_identity.py`, `test_actor.py` | parametrised cases annotate `type[PublicId] \| type[EventId]` / `type[Actor] \| type[SystemActor]` instead of a bare `type`, which declared neither `.new()` nor `.parse()` |
| `tests/core/test_events.py` | the ill-typed registry payload is assembled as `dict[str, Any]`, since being ill-typed is the point of the case |

Four deliberate negative-test lines carry a narrow `# type: ignore[<code>]` with the reason.

Result: **`mypy .` reports no issues in 69 source files.**

## 4. Dependency bounds

`django-stubs` and `mypy` were declared with an open `>=`. `uv.lock` pins the actual build, but
`uv lock --upgrade` could cross a major on its own. They are now `>=6.1.0,<6.2` and `>=2.3.1,<2.4`.
Every other dependency was already `==`-pinned, and every pin is the current upstream release as of
this date.

## 5. Version control

Slice 1 §11 recorded "the repository is not under version control and no CI system exists", and
Slice 1 §2 described the lockfile as checked in — which it could not be. The repository is now
initialised, with `uv.lock` tracked, so the build is reproducible.

`.gitignore` gained `.import_linter_cache/`; it already covered the pytest, ruff and mypy caches.

## 6. Enforcement

`make check` previously ran `lint arch test django-check`. Formatting was available as `fmt` but
never gated, and five files had drifted; mypy was installed but never invoked, which is why the
plugin crash went unnoticed. The target is now:

```
check: fmt-check lint types arch test django-check
```

`make check` remains the provider-agnostic entry point a CI job will call (Slice 1 §11).

## 7. Deferred, unchanged

| Deferral | To whom |
|---|---|
| Celery app, broker, routing, queue provisioning | the slice that runs the first workload (item 14 §15) |
| A cache client, and `redis[hiredis]` with it | the slice that adds the first cache read |
| DRF, `wsgi.py`/`asgi.py`, psycopg pool sizing and timeouts | unchanged from Slice 1 §11 |
| `psycopg[binary]` → a source/C build for production | the slice that sets pool sizing and timeouts; upstream treats the binary wheel as the development convenience |
| `per-file-ignores` for `**/migrations/*.py` | the entry is in place; the first migration makes it load-bearing |
| CI job wiring | a CI system still does not exist; `make check` is ready for one |

No infrastructure gate was opened, and no `LATER` module was created.

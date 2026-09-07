.PHONY: install fmt fmt-check lint types arch-imports arch-static arch test test-db \
        django-check migrations-check check check-all

install:  ## Create/refresh the pinned environment
	uv sync

fmt:
	uv run ruff format .

fmt-check:  ## Formatting is gated, not just available
	uv run ruff format --check .

lint:
	uv run ruff check .

types:  ## Strict on production packages; tests/tools relax annotation rules only
	uv run mypy .

arch-imports:  ## Frozen import contracts (Phase 0 item 3 §15.1)
	uv run lint-imports

arch-static:  ## AST/static architecture rules (item 3 §15.2, item 14 §19)
	uv run python -m tools.arch_check .

arch: arch-imports arch-static

test:  ## The unit tier: contacts no database, so it runs anywhere
	uv run pytest -m "not integration"

test-db:  ## The integration tier: needs a live PostgreSQL and a role that may CREATEDB
	uv run pytest -m integration

django-check:  ## Django system checks; `tests.settings` re-exports the launch settings
	DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py check

migrations-check:  ## A model edited after its migration passes every other gate and is wrong
	DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py makemigrations --check --dry-run

check: fmt-check lint types arch test django-check migrations-check

check-all: check test-db  ## Everything, including the tier that needs PostgreSQL

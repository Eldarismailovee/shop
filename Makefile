.PHONY: install fmt fmt-check lint types arch-imports arch-static arch test django-check check

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

test:
	uv run pytest

django-check:  ## Django system checks; `tests.settings` re-exports the launch settings
	DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py check

check: fmt-check lint types arch test django-check

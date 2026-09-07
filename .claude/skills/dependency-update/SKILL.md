---
name: dependency-update
description: Add, update, or use a version-sensitive Python/Django/DRF/Celery/PostgreSQL/JS dependency or API. Use when correctness depends on current package behavior.
effort: high
---
# Dependency / current API workflow
1. Inspect `pyproject.toml`/lockfile and installed version before assuming an API.
2. Prefer existing dependencies and standard-library/framework capabilities.
3. If changing a dependency or relying on recent behavior, verify against official upstream documentation/changelog when web access is available.
4. Avoid blog-only guidance for security/version claims.
5. Change only the dependency required by the task; do not perform opportunistic upgrades.
6. Check compatibility with Python/Django/PostgreSQL baseline and run the smallest relevant integration tests.
7. Record a notable architecture-impacting version decision in a **new** ADR; never edit an accepted ADR in place. Routine patch upgrades need no ADR.
8. Do not add a dependency that only a `LATER` module would use, and do not pull in a closed infrastructure gate (search engine, connection pooler, replica tooling, PostGIS).

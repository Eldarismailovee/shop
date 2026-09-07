---
paths:
  - "domains/**/*.py"
  - "domains/**/tests.py"
  - "domains/**/tests/**/*.py"
---
# Domain layer rules
- A domain imports only its own package and `core`.
- External callers use this domain's `public.py`; do not expose ORM models or QuerySets.
- Keep domain mutations in services/state machines and reads in selectors.
- Use immutable DTO/value objects at the boundary.
- If code needs another domain, move orchestration to `application/` instead of adding a cross-domain import.
- Object ownership rules belong in policies/scoped selectors, not only in views.

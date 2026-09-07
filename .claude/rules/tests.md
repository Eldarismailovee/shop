---
paths:
  - "tests/**/*.py"
  - "tests.py"
  - "**/tests.py"
  - "**/tests/**/*.py"
  - "**/test_*.py"
  - "**/conftest.py"
---
# Test rules
- Test behavior/invariants, not implementation trivia.
- Critical classes: unit, integration, architecture contracts, security/IDOR, concurrency/idempotency, query budget/N+1, event compatibility.
- Add regression tests for every fixed production-class bug.
- Keep concurrency tests deterministic around the invariant being proven.
- Prefer targeted test selection during iteration; run broader suites at the final gate when scope requires it.

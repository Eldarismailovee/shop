"""Static architecture checks for the frozen Phase 0 dependency graph.

`import-linter` owns the import-graph contracts it can state over packages that already
exist (`pyproject.toml`, `[tool.importlinter]`). This checker owns the rules it cannot:
the `PUBLIC ONLY` / `PORT ONLY` / `SPECIAL CASE` cells, the module-shape rules of item 3
§15.2, and item 14 §19's fake-compatibility shapes.
"""

from tools.arch_check.model import Violation
from tools.arch_check.rules import RULES, check_tree

__all__ = ["RULES", "Violation", "check_tree"]

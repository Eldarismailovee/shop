"""Fixture-tree helper for the architecture harness.

The enforcement tests need modules that deliberately break the frozen matrix. Writing
them into the real source tree would create production packages whose only purpose is to
be illegal, so each case is materialised as a throwaway tree under `tmp_path` instead.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from tools.arch_check import check_tree


@pytest.fixture
def arch_rules() -> Callable[[Path, Mapping[str, str]], set[str]]:
    """Materialise a source tree and return the set of rule ids it violates."""

    def run(root: Path, files: Mapping[str, str]) -> set[str]:
        for relative, source in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
            # Every ancestor inside a family needs to be a package for dotted resolution.
            for parent in path.parents:
                if parent == root:
                    break
                init = parent / "__init__.py"
                if not init.exists():
                    init.write_text("", encoding="utf-8")
        return {violation.rule for violation in check_tree(root)}

    return run

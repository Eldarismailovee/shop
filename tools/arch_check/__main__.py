"""CLI: `python -m tools.arch_check [root]`."""

from __future__ import annotations

import sys
from pathlib import Path

from tools.arch_check.rules import check_tree


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    violations = check_tree(root)
    for violation in violations:
        print(violation)
    if violations:
        print(f"\n{len(violations)} architecture violation(s).", file=sys.stderr)
        return 1
    print("arch_check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

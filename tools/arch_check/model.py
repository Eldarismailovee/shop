"""Source discovery and the module model the architecture rules run over."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

#: Top-level package families that make up the frozen source graph (Phase 0 item 3 §4).
SOURCE_FAMILIES: tuple[str, ...] = (
    "core",
    "domains",
    "application",
    "interfaces",
    "integrations",
    "tasks",
    "config",
    "tests",
)

#: Families whose second path segment is an ownership boundary (`domains/<x>`,
#: `application/<a>`, `integrations/<v>`).
OWNER_FAMILIES: frozenset[str] = frozenset({"domains", "application", "integrations"})


@dataclass(frozen=True, slots=True)
class Violation:
    """One architecture-rule failure, anchored at a source location."""

    rule: str
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}"


@dataclass(frozen=True, slots=True)
class ImportRef:
    """A resolved import edge: where it points, and where it was written."""

    target: str
    line: int
    #: The statement as written, for messages (`import x` / `from x import y`).
    text: str


@dataclass(frozen=True, slots=True)
class SourceModule:
    root: Path
    path: Path
    dotted: str
    is_package_init: bool
    tree: ast.Module
    imports: tuple[ImportRef, ...]

    @property
    def rel(self) -> str:
        return self.path.relative_to(self.root).as_posix()

    @property
    def family(self) -> str:
        return self.dotted.split(".")[0]

    @property
    def owner(self) -> str | None:
        """`domains.catalog`, `application.checkout`, `integrations.maib` — else None."""
        parts = self.dotted.split(".")
        if self.family in OWNER_FAMILIES and len(parts) >= 2:
            return ".".join(parts[:2])
        return None

    @property
    def is_migration(self) -> bool:
        return "migrations" in self.rel.split("/")

    @property
    def basename(self) -> str:
        return self.path.name


def under(target: str, prefix: str) -> bool:
    """True when `target` is `prefix` itself or a module inside it."""
    return target == prefix or target.startswith(prefix + ".")


def _dotted_for(root: Path, path: Path) -> tuple[str, bool]:
    rel = path.relative_to(root)
    parts = list(rel.parts)
    is_init = parts[-1] == "__init__.py"
    parts[-1] = parts[-1].removesuffix(".py")
    if is_init:
        parts.pop()
    return ".".join(parts), is_init


def _raw_imports(
    tree: ast.Module, dotted: str, is_init: bool
) -> list[tuple[str, tuple[str, ...], int, str]]:
    """Collect `(base module, imported names, line, text)` for every import statement."""
    found: list[tuple[str, tuple[str, ...], int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, (), node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = dotted.split(".")
                package = parts if is_init else parts[:-1]
                if node.level > 1:
                    package = package[: -(node.level - 1)]
                base = ".".join([*package, base] if base else package)
            names = tuple(alias.name for alias in node.names)
            text = f"from {base or '.'} import {', '.join(names)}"
            found.append((base, names, node.lineno, text))
    return found


def discover(root: Path) -> list[SourceModule]:
    """Parse every source module under the known families of `root`."""
    files: list[tuple[Path, str, bool]] = []
    for family in SOURCE_FAMILIES:
        family_dir = root / family
        if not family_dir.is_dir():
            continue
        for path in sorted(family_dir.rglob("*.py")):
            dotted, is_init = _dotted_for(root, path)
            files.append((path, dotted, is_init))

    modules: list[SourceModule] = []
    for path, dotted, is_init in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        refs: list[ImportRef] = []
        for base, names, line, text in _raw_imports(tree, dotted, is_init):
            if not base:
                continue
            if not names:
                refs.append(ImportRef(base, line, text))
                continue
            # `from M import n` is recorded as the full dotted path `M.n`, whether `n` is
            # a submodule or a symbol. Every boundary rule asks "does this reach past
            # <owner>.public / into models", which the full path answers correctly in
            # both cases without needing to know which one it is.
            for name in names:
                refs.append(ImportRef(f"{base}.{name}", line, text))
        modules.append(
            SourceModule(
                root=root,
                path=path,
                dotted=dotted,
                is_package_init=is_init,
                tree=tree,
                imports=tuple(refs),
            )
        )
    return modules

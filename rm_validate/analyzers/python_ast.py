"""Adapter: Python imports via the stdlib ``ast`` (precise, graph-capable).

``ast`` is stdlib, so this does not violate "only external dep: PyYAML". It is
more robust than regex for Python and backs both containment checks and the
import graph used by ``no_circular_dependencies``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from rm_validate.analyzers.base import ImportAnalyzer, RawImport


@dataclass
class PyIndex:
    full: dict[str, str]  # dotted-from-repo-root -> rel
    suffix: dict[str, frozenset[str]]  # dotted suffix -> {rel}


class PythonAnalyzer(ImportAnalyzer):
    LANGUAGES: ClassVar[frozenset[str]] = frozenset({".py"})
    supports_graph: ClassVar[bool] = True

    def extract_imports(self, repo: Path, rel: str) -> list[RawImport]:
        try:
            tree = ast.parse((repo / rel).read_text(encoding="utf-8", errors="ignore"))
        except (SyntaxError, ValueError, OSError):
            return []
        out: list[RawImport] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                out.extend(RawImport(module=a.name) for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                level = node.level or 0
                module = node.module or ""
                # One unit per imported name: ``from pkg import b`` should be
                # able to resolve to the submodule ``pkg/b.py``, not just ``pkg``.
                for alias in node.names:
                    out.append(RawImport(module=module, level=level, names=(alias.name,)))
                if not node.names:
                    out.append(RawImport(module=module, level=level))
        return out

    def prepare(self, rel_files: list[str]) -> PyIndex:
        full: dict[str, str] = {}
        suffix: dict[str, set[str]] = {}
        for rel in rel_files:
            if not rel.endswith(".py"):
                continue
            parts = _module_parts(rel)
            if not parts:
                continue
            full[".".join(parts)] = rel
            for start in range(len(parts)):
                suffix.setdefault(".".join(parts[start:]), set()).add(rel)
        return PyIndex(full=full, suffix={k: frozenset(v) for k, v in suffix.items()})

    def resolve(self, importer_rel: str, imp: RawImport, index: PyIndex) -> str | None:
        for candidate in self._candidates(importer_rel, imp):
            target = self._lookup(candidate, index)
            if target is not None and target != importer_rel:
                return target
        return None

    def _candidates(self, importer_rel: str, imp: RawImport) -> list[str]:
        # Most-specific first: try the name-qualified module (a submodule) before
        # the bare package, so ``from pkg import b`` prefers ``pkg.b`` over ``pkg``.
        if imp.level and imp.level > 0:
            base = _module_parts(importer_rel)[:-1]  # importer's package
            up = imp.level - 1
            anchor = base[: len(base) - up] if up <= len(base) else []
            prefix = anchor + ([imp.module] if imp.module else [])
            qualified = [".".join(prefix + [n]) for n in imp.names]
            base_name = [".".join(prefix)] if prefix else []
            return [n for n in qualified + base_name if n]
        if not imp.module:
            return []
        qualified = [f"{imp.module}.{n}" for n in imp.names]
        return qualified + [imp.module]

    def _lookup(self, dotted: str, index: PyIndex) -> str | None:
        parts = dotted.split(".")
        for end in range(len(parts), 0, -1):
            candidate = ".".join(parts[:end])
            if candidate in index.full:
                return index.full[candidate]
            matches = index.suffix.get(candidate)
            if matches and len(matches) == 1:
                return next(iter(matches))
        return None


def _module_parts(rel: str) -> list[str]:
    parts = rel[:-3].split("/") if rel.endswith(".py") else rel.split("/")
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return parts

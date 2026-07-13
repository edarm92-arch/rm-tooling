"""Adapter: TS/JS imports via regex (containment only — NOT graph-capable).

Regex is enough to answer "does this file import something matching a forbidden
pattern?" (a containment test). It is NOT enough to build a precise TS import
graph: path aliases (``@/…``), barrels (``index.ts``) and ``tsconfig.paths``
make resolution genuinely hard, so ``supports_graph`` is False. Pretending to
graph TS with regex would be theatre — cycle detection over TS is deferred, not
faked.

Resolution here handles RELATIVE specifiers (``./x``, ``../y``) by path — enough
to catch a forbidden import into a sibling layer. Bare/aliased specifiers are
left unresolved (a rare, acknowledged false negative for containment).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

from rm_validate.analyzers.base import ImportAnalyzer, RawImport

_SPECIFIER = r"['\"]([^'\"]+)['\"]"
_PATTERNS = [
    re.compile(rf"\bimport\b[^;'\"]*\bfrom\s*{_SPECIFIER}"),
    re.compile(rf"\bexport\b[^;'\"]*\bfrom\s*{_SPECIFIER}"),
    re.compile(rf"\bimport\s*{_SPECIFIER}"),            # side-effect import 'x'
    re.compile(rf"\brequire\s*\(\s*{_SPECIFIER}\s*\)"),
    re.compile(rf"\bimport\s*\(\s*{_SPECIFIER}\s*\)"),   # dynamic import('x')
]
_CANDIDATE_SUFFIXES = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_INDEX_FILES = ("index.ts", "index.tsx", "index.js", "index.jsx")


class TsJsAnalyzer(ImportAnalyzer):
    LANGUAGES: ClassVar[frozenset[str]] = frozenset(
        {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
    )
    supports_graph: ClassVar[bool] = False

    def extract_imports(self, repo: Path, rel: str) -> list[RawImport]:
        try:
            text = (repo / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        seen: set[str] = set()
        out: list[RawImport] = []
        for pattern in _PATTERNS:
            for m in pattern.finditer(text):
                spec = m.group(1)
                if spec in seen:
                    continue
                seen.add(spec)
                out.append(RawImport(module=spec, relative=spec.startswith(".")))
        return out

    def prepare(self, rel_files: list[str]) -> frozenset[str]:
        return frozenset(rel_files)

    def resolve(self, importer_rel: str, imp: RawImport, index: frozenset[str]) -> str | None:
        if not imp.relative:
            return None  # bare/aliased: unresolved without tsconfig (acknowledged)
        base = importer_rel.rsplit("/", 1)[0] if "/" in importer_rel else ""
        target = _normalize(f"{base}/{imp.module}" if base else imp.module)
        for suffix in _CANDIDATE_SUFFIXES:
            candidate = target + suffix
            if candidate in index and candidate != importer_rel:
                return candidate
        for index_file in _INDEX_FILES:
            candidate = f"{target}/{index_file}"
            if candidate in index:
                return candidate
        return None


def _normalize(path: str) -> str:
    """Resolve ``.`` and ``..`` segments in a posix-like relative path."""
    stack: list[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if stack:
                stack.pop()
        else:
            stack.append(part)
    return "/".join(stack)

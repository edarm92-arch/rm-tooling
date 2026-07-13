"""Analyzer registry: extension -> adapter, plus language-grouping helpers.

Adding a language means appending an adapter to ``_ANALYZERS`` — the checks
never change.
"""

from __future__ import annotations

from collections import defaultdict

from rm_validate.analyzers.base import ImportAnalyzer
from rm_validate.analyzers.python_ast import PythonAnalyzer
from rm_validate.analyzers.regex_imports import TsJsAnalyzer

_ANALYZERS: list[ImportAnalyzer] = [PythonAnalyzer(), TsJsAnalyzer()]

_BY_EXT: dict[str, ImportAnalyzer] = {
    ext: analyzer for analyzer in _ANALYZERS for ext in analyzer.LANGUAGES
}


def analyzer_for(ext: str) -> ImportAnalyzer | None:
    return _BY_EXT.get(ext.lower())


def supported_extensions() -> frozenset[str]:
    return frozenset(_BY_EXT)


def graph_extensions() -> frozenset[str]:
    return frozenset(ext for ext, a in _BY_EXT.items() if a.supports_graph)


def group_by_ext(rel_files: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for rel in rel_files:
        ext = _ext(rel)
        groups[ext].append(rel)
    return dict(groups)


def _ext(rel: str) -> str:
    name = rel.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    return name[dot:].lower() if dot >= 0 else ""

"""First-party Python import graph (backs ``no_circular_dependencies``).

Graph precision is only available for Python (via the ast adapter); this module
builds the graph over a set of Python files. Cross-language cycle detection is
deliberately out of scope for v0.1.0 — see the coverage gate in
``circular_deps``, which fails rather than pretend.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rm_validate.analyzers.python_ast import PythonAnalyzer


@dataclass
class ImportGraph:
    files: list[str]  # repo-relative posix paths of the analyzed .py files
    edges: dict[str, set[str]]  # importer -> imported first-party files (in scope)


def build_graph(repo: Path, py_files: list[Path]) -> ImportGraph:
    rels = [p.relative_to(repo).as_posix() for p in py_files]
    return build_graph_from_rels(repo, rels)


def build_graph_from_rels(repo: Path, rels: list[str]) -> ImportGraph:
    analyzer = PythonAnalyzer()
    index = analyzer.prepare(rels)
    in_scope = set(rels)
    edges: dict[str, set[str]] = {rel: set() for rel in rels}
    for rel in rels:
        for imp in analyzer.extract_imports(repo, rel):
            target = analyzer.resolve(rel, imp, index)
            if target is not None and target != rel and target in in_scope:
                edges[rel].add(target)
    return ImportGraph(files=rels, edges=edges)

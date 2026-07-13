from __future__ import annotations

from pathlib import Path

from rm_validate.checks.fitness.graph import build_graph


def _py_files(repo: Path) -> list[Path]:
    return sorted(repo.rglob("*.py"))


def test_absolute_import_edge(make_repo) -> None:
    repo = make_repo({
        "pkg/__init__.py": "",
        "pkg/a.py": "from pkg import b\n",
        "pkg/b.py": "x = 1\n",
    }, with_adr=False, with_changelog=False)
    graph = build_graph(repo, _py_files(repo))
    assert "pkg/b.py" in graph.edges["pkg/a.py"]


def test_relative_import_edge(make_repo) -> None:
    repo = make_repo({
        "pkg/__init__.py": "",
        "pkg/a.py": "from . import b\n",
        "pkg/b.py": "x = 1\n",
    }, with_adr=False, with_changelog=False)
    graph = build_graph(repo, _py_files(repo))
    assert "pkg/b.py" in graph.edges["pkg/a.py"]


def test_cycle_detected(make_repo) -> None:
    from rm_validate.checks.fitness.circular_deps import _find_cycles

    repo = make_repo({
        "pkg/__init__.py": "",
        "pkg/a.py": "from pkg import b\n",
        "pkg/b.py": "from pkg import a\n",
    }, with_adr=False, with_changelog=False)
    graph = build_graph(repo, _py_files(repo))
    cycles = _find_cycles(graph.edges)
    assert cycles, "expected a cycle"
    flat = {n for c in cycles for n in c}
    assert {"pkg/a.py", "pkg/b.py"} <= flat


def test_third_party_import_ignored(make_repo) -> None:
    repo = make_repo({
        "pkg/__init__.py": "",
        "pkg/a.py": "import os\nimport sqlalchemy\n",
    }, with_adr=False, with_changelog=False)
    graph = build_graph(repo, _py_files(repo))
    assert graph.edges["pkg/a.py"] == set()

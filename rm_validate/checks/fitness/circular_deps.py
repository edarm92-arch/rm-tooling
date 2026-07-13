"""Fitness: ``no_circular_dependencies`` (import graph — Python only in v0.1.0).

Cycle detection needs a precise, complete graph. That is only available for
Python (ast). The check's scope is ``graph_scope`` (default ``**/*.py``); if the
scope matches files of a language without graph support (e.g. TS/JS), the
coverage gate fails with "config incompleta" rather than pass an empty, green
result — pretending to graph TS with regex would be theatre.
"""

from __future__ import annotations

from rm_validate.analyzers import registry as analyzers
from rm_validate.checks.base import CheckContext, Finding, Severity
from rm_validate.checks.fitness.containment import assess_coverage, coverage_findings
from rm_validate.checks.fitness.graph import build_graph_from_rels

CHECK_NAME = "no_circular_dependencies"


def run(ctx: CheckContext) -> list[Finding]:
    scope = ctx.config.graph_scope
    cov = assess_coverage(ctx, scope, analyzers.graph_extensions())
    findings: list[Finding] = coverage_findings(CHECK_NAME, cov, needs_graph=True)

    graph = build_graph_from_rels(ctx.repo, cov.analyzed)
    cycles = _find_cycles(graph.edges)
    seen: set[frozenset[str]] = set()
    for cycle in cycles:
        sig = frozenset(cycle)
        if sig in seen:
            continue
        seen.add(sig)
        cycle = _canonical(cycle)
        chain = " -> ".join(cycle + [cycle[0]])
        findings.append(
            Finding(
                check=CHECK_NAME,
                severity=Severity.ERROR,
                message=f"circular import cycle: {chain}",
                rule="no import cycles among first-party modules",
                value=chain,
                limit="acyclic",
                path=cycle[0],
            )
        )
    return findings


def _canonical(cycle: list[str]) -> list[str]:
    """Rotate a cycle to start at its smallest node for a stable identity."""
    if not cycle:
        return cycle
    i = cycle.index(min(cycle))
    return cycle[i:] + cycle[:i]


def _find_cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    """Return cycles via DFS, coloring nodes white/grey/black."""
    cycles: list[list[str]] = []
    color: dict[str, int] = {}  # 0=unvisited, 1=on-stack, 2=done
    for start in edges:
        if color.get(start, 0) == 0:
            _dfs(start, edges, color, [], cycles)
    return cycles


def _dfs(
    node: str,
    edges: dict[str, set[str]],
    color: dict[str, int],
    path: list[str],
    cycles: list[list[str]],
) -> None:
    color[node] = 1
    path.append(node)
    for nxt in sorted(edges.get(node, ())):
        state = color.get(nxt, 0)
        if state == 0:
            _dfs(nxt, edges, color, path, cycles)
        elif state == 1 and nxt in path:
            # Back edge -> cycle is the path slice from nxt to current node.
            idx = path.index(nxt)
            cycles.append(path[idx:])
    path.pop()
    color[node] = 2

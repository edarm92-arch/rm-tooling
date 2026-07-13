"""Shared machinery for import-based fitness checks + the language coverage gate.

The invariant (PARTE 5): a check that cannot analyze the files its globs matched
never reports success. So before running, every check assesses coverage; any
matched file in an unsupported language yields a config-integrity failure that
blocks even in ``warning`` mode. "Could not analyze" must never masquerade as
"no violations".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rm_validate.analyzers import registry as analyzers
from rm_validate.checks.base import CheckContext, Finding, Severity
from rm_validate.globs import match_any

CHECK_NAME = "language_coverage"


@dataclass
class Coverage:
    matched: list[str] = field(default_factory=list)
    analyzed: list[str] = field(default_factory=list)
    # ext -> files that a check's globs matched but cannot be analyzed.
    unsupported: dict[str, list[str]] = field(default_factory=dict)


def assess_coverage(
    ctx: CheckContext, globs: list[str], supported_exts: frozenset[str]
) -> Coverage:
    cov = Coverage()
    for rel in ctx.all_rel():
        if not match_any(rel, globs):
            continue
        cov.matched.append(rel)
        ext = _ext(rel)
        if ext in supported_exts and analyzers.analyzer_for(ext) is not None:
            cov.analyzed.append(rel)
        else:
            cov.unsupported.setdefault(ext, []).append(rel)
    return cov


def coverage_findings(check_name: str, cov: Coverage, *, needs_graph: bool) -> list[Finding]:
    findings: list[Finding] = []
    for ext, files in sorted(cov.unsupported.items()):
        pretty = ext or "(no extension)"
        if needs_graph and analyzers.analyzer_for(ext) is not None:
            reason = "import graph not supported for this language in v0.1.0"
        else:
            reason = "language not supported in v0.1.0"
        findings.append(
            Finding(
                check=check_name,
                severity=Severity.ERROR,
                config_integrity=True,
                message=(
                    f"config incompleta: {check_name} matched {len(files)} {pretty} "
                    f"file(s) — {reason}. Narrow the glob to a supported language, "
                    f"or set the check to false."
                ),
                rule="a check must be able to analyze every file its globs match",
                value=f"{len(files)} {pretty} file(s) unanalyzable",
                limit="all matched files in a supported language",
                path=files[0],
            )
        )
    return findings


def resolve_edges(ctx: CheckContext, files: list[str]) -> list[tuple[str, str]]:
    """Resolve first-party import edges (importer_rel, target_rel) for ``files``."""
    edges: list[tuple[str, str]] = []
    for rel in files:
        analyzer = analyzers.analyzer_for(_ext(rel))
        if analyzer is None:
            continue
        index = ctx.index_for(analyzer)
        for imp in analyzer.extract_imports(ctx.repo, rel):
            target = analyzer.resolve(rel, imp, index)
            if target is not None:
                edges.append((rel, target))
    return edges


def _ext(rel: str) -> str:
    name = rel.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    return name[dot:].lower() if dot >= 0 else ""

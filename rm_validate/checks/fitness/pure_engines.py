"""Fitness: ``engines_must_be_pure`` (Python only, via ast).

Engines are pure, generic and caller-agnostic (core §5): they may import stdlib
and third-party libraries, but must not import first-party application modules
outside the engines layer. Deciding what is "first-party" reliably needs
resolution, which is precise only with ``ast`` — so this check supports Python
only. Engine globs that match another language fail the coverage gate.
"""

from __future__ import annotations

from rm_validate.analyzers.python_ast import PythonAnalyzer
from rm_validate.checks.base import CheckContext, Finding, Severity
from rm_validate.checks.fitness.containment import (
    assess_coverage,
    coverage_findings,
    resolve_edges,
)
from rm_validate.globs import match_any

CHECK_NAME = "engines_must_be_pure"
SUPPORTED = PythonAnalyzer.LANGUAGES


def run(ctx: CheckContext) -> list[Finding]:
    engines_globs = ctx.config.layering_patterns.get("engines")
    if not engines_globs:
        return []  # layering config lock reports the missing key separately
    cov = assess_coverage(ctx, engines_globs, SUPPORTED)
    findings: list[Finding] = coverage_findings(CHECK_NAME, cov, needs_graph=False)
    for importer, target in resolve_edges(ctx, cov.analyzed):
        # Importing another engine is fine; importing the rest of the app is not.
        if match_any(target, engines_globs):
            continue
        findings.append(
            Finding(
                check=CHECK_NAME,
                severity=Severity.ERROR,
                message=f"engine {importer} imports first-party module {target}",
                rule="engines must be pure (no imports of first-party app modules)",
                value=f"{importer} -> {target}",
                limit="engines import only stdlib/third-party or other engines",
                path=importer,
            )
        )
    return findings

"""Generic forbidden import edges (multi-language containment).

Files matching any ``src`` glob must not import first-party modules whose file
matches any ``dst`` glob. Backs the layering rules and user-declared
``forbidden_imports``. Containment is safe with regex, so this family supports
Python (via ast) and TS/JS (via regex). Files in an unsupported language fail
the coverage gate rather than passing empty.
"""

from __future__ import annotations

from rm_validate.analyzers import registry as analyzers
from rm_validate.checks.base import CheckContext, Finding, Severity
from rm_validate.checks.fitness.containment import (
    assess_coverage,
    coverage_findings,
    resolve_edges,
)
from rm_validate.globs import match_any

CHECK_NAME = "forbidden_deps"

# Containment checks can analyze every language with an adapter.
CONTAINMENT_LANGUAGES = analyzers.supported_extensions()


def forbidden_edge_findings(
    ctx: CheckContext,
    *,
    check_name: str,
    rule: str,
    src_globs: list[str],
    dst_globs: list[str],
    supported_exts: frozenset[str] = CONTAINMENT_LANGUAGES,
    severity: Severity = Severity.ERROR,
) -> list[Finding]:
    """Report first-party imports from ``src`` files into ``dst`` files."""
    cov = assess_coverage(ctx, src_globs, supported_exts)
    findings: list[Finding] = coverage_findings(check_name, cov, needs_graph=False)
    for importer, target in resolve_edges(ctx, cov.analyzed):
        if match_any(target, dst_globs):
            findings.append(
                Finding(
                    check=check_name,
                    severity=severity,
                    message=f"{importer} imports {target} (forbidden by {rule})",
                    rule=rule,
                    value=f"{importer} -> {target}",
                    limit="no such import",
                    path=importer,
                )
            )
    return findings


def run(ctx: CheckContext) -> list[Finding]:
    """Apply the target repo's declared ``forbidden_imports`` rules."""
    findings: list[Finding] = []
    for rule in ctx.config.forbidden_imports:
        findings.extend(
            forbidden_edge_findings(
                ctx,
                check_name=CHECK_NAME,
                rule=rule.name,
                src_globs=rule.src,
                dst_globs=rule.dst,
            )
        )
    return findings

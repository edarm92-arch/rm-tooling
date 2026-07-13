"""Universal: hand-declared excludes are visible, never silent.

Structural excludes (``node_modules``, ``.venv``, ``dist``, ...) are hygiene and
stay silent. A hand-declared exclude in ``modularity.exclude_globs`` removes real
files from the checks that scan the tree (file limits, secrets, the import-based
fitness checks), so it is surfaced as a WARNING naming the path and the affected
checks. The base universal is never turned off in silence.

Capability inference is deliberately NOT in the affected list: it no longer
honors any consumer-configurable exclude, so it cannot be narrowed to hide
evidence from the capability-mismatch lock.
"""

from __future__ import annotations

from rm_validate.checks.base import CheckContext, Finding, Severity

CHECK_NAME = "inference_exclusion"
_AFFECTED = "file_limits, secrets_scan, and the import-based fitness checks"


def run(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    for glob in ctx.config.modularity.extra_excludes:
        findings.append(
            Finding(
                check=CHECK_NAME,
                severity=Severity.WARNING,
                message=(
                    f"hand-declared exclude '{glob}' removes files from {_AFFECTED}. "
                    f"Structural excludes stay silent; this one is surfaced so the "
                    f"reduced scan surface is never invisible."
                ),
                rule="hand-declared excludes are reported, not silent",
                value=glob,
                limit="structural excludes only (node_modules, .venv, dist, ...)",
                path=None,
            )
        )
    return findings

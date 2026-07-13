"""Integrity lock: an enabled layering fitness function needs its layer globs.

If ``fitness_functions.<x>: true`` but a key ``<x>`` requires is absent from
``layering_patterns``, ``check`` fails with
``config incompleta: falta layering_patterns.<key> para <x>``. This runs even in
``warning`` mode — it is config integrity (the repo asked for the check but did
not supply the data to run it), not the severity of a code violation.
"""

from __future__ import annotations

from rm_validate.checks.base import CheckContext, Finding, Severity

CHECK_NAME = "layering_config"


def run(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    for fitness_function, key in ctx.config.missing_layering():
        findings.append(
            Finding(
                check=CHECK_NAME,
                severity=Severity.ERROR,
                config_integrity=True,
                message=(
                    f"config incompleta: falta layering_patterns.{key} para {fitness_function}"
                ),
                rule=f"{fitness_function} requires layering_patterns.{key}",
                value=f"layering_patterns.{key} missing",
                limit="declare the glob(s) for this layer",
            )
        )
    return findings

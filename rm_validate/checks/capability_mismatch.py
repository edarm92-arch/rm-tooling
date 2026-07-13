"""Integrity lock: declared capabilities must match what the code shows.

Asymmetric, on purpose (core §0 — the profile lowers bureaucracy of what you
do NOT have, never security of what you DO):

* **Under-declaring** (declared ``false`` but the code shows evidence) is a
  config-integrity FAILURE — it blocks even in ``warning`` mode, because it
  silences a rule that should apply (risk).
* **Over-declaring** (declared ``true`` but no evidence) is only a WARNING —
  it merely adds the repo's own overhead; it does not weaken anything.

``enforcement.capability_mismatch_fails`` (default true) controls whether
under-declaration blocks; the detection itself always runs.
"""

from __future__ import annotations

from rm_validate.checks.base import CheckContext, Finding, Severity

CHECK_NAME = "capability_mismatch"


def run(ctx: CheckContext) -> list[Finding]:
    declared = ctx.config.capabilities
    inferred = ctx.inferred.capabilities
    strict = ctx.config.enforcement.capability_mismatch_fails

    findings: list[Finding] = []
    for cap, evidence in inferred.items():
        is_declared = bool(declared.get(cap, False))
        if evidence.detected and not is_declared:
            # Under-declaration: the code has it but the policy denies it.
            findings.append(
                Finding(
                    check=CHECK_NAME,
                    severity=Severity.ERROR,
                    config_integrity=strict,
                    message=(
                        f"capability '{cap}' is declared false but the code shows evidence: "
                        + "; ".join(evidence.evidence)
                    ),
                    rule="declared capabilities match code (no under-declaration)",
                    value=f"{cap}=false",
                    limit=f"{cap}=true (evidence found)",
                )
            )
        elif is_declared and not evidence.detected:
            # Over-declaration: only the repo's own overhead, so a soft warning.
            findings.append(
                Finding(
                    check=CHECK_NAME,
                    severity=Severity.WARNING,
                    message=f"capability '{cap}' is declared true but no code evidence was found",
                    rule="declared capabilities have supporting evidence",
                    value=f"{cap}=true",
                    limit="evidence in code, or drop the capability",
                )
            )
    return findings

"""Human-readable reporting and exit-code policy.

Exit codes:
* Any config-integrity finding -> exit 1 (always, even in ``warning`` mode).
* ``blocking`` mode + any error-severity finding -> exit 1.
* Otherwise exit 0 (warnings never block).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rm_validate.baseline import BaselineStats
from rm_validate.checks.base import Finding, Severity

EXIT_OK = 0
EXIT_FAIL = 1


@dataclass
class Outcome:
    findings: list[Finding]
    mode: str = "warning"
    baseline: BaselineStats | None = None
    degraded: bool = False  # no policy file -> neutral, advisory-only
    ran_checks: list[str] = field(default_factory=list)

    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARNING]

    def integrity(self) -> list[Finding]:
        return [f for f in self.findings if f.config_integrity]

    def exit_code(self) -> int:
        if self.degraded:
            return EXIT_OK
        if self.integrity():
            return EXIT_FAIL
        if self.mode == "blocking" and self.errors():
            return EXIT_FAIL
        return EXIT_OK


def render(outcome: Outcome) -> str:
    if outcome.degraded:
        return _render_degraded()

    lines: list[str] = []
    lines.append(f"rm-validate check — mode: {outcome.mode}")
    if outcome.ran_checks:
        lines.append(f"checks run: {', '.join(outcome.ran_checks)}")
    lines.append("")

    if not outcome.findings:
        lines.append("PASS — no findings.")
    else:
        for f in _ordered(outcome.findings):
            lines.append(_render_finding(f))

    lines.append("")
    lines.append(_summary_line(outcome))
    if outcome.baseline is not None:
        lines.append(_baseline_line(outcome.baseline))
    lines.append(f"exit code: {outcome.exit_code()}")
    return "\n".join(lines)


def _render_degraded() -> str:
    return (
        "rm-validate check — no rm-policy.yaml found.\n"
        "\n"
        "Nothing to validate yet: this repo has no policy. The validator is an\n"
        "advisor until rules are declared, then a judge.\n"
        "\n"
        "Next step: run `rm-validate init` to infer capabilities from the code,\n"
        "get a suggested profile, and write a commented rm-policy.yaml.\n"
        "\n"
        "exit code: 0 (neutral — graceful degradation, not a failure)"
    )


def _render_finding(f: Finding) -> str:
    tag = "INTEGRITY" if f.config_integrity else f.severity.value.upper()
    where = f.path or "-"
    detail = ""
    if f.value or f.limit:
        detail = f"  [{f.value} vs {f.limit}]"
    return f"  {tag:9} {f.check:34} {where}\n      {f.message}{detail}"


def _ordered(findings: list[Finding]) -> list[Finding]:
    # Integrity first, then errors, then warnings; stable within a group.
    def rank(f: Finding) -> int:
        if f.config_integrity:
            return 0
        return 1 if f.severity is Severity.ERROR else 2

    return sorted(findings, key=rank)


def _summary_line(outcome: Outcome) -> str:
    return (
        f"summary: {len(outcome.integrity())} integrity, "
        f"{len(outcome.errors())} error, {len(outcome.warnings())} warning"
    )


def _baseline_line(stats: BaselineStats) -> str:
    if stats.created:
        return f"baseline: created with {stats.inventoried} pre-existing violation(s) as debt."
    parts = [
        f"baseline: {stats.inventoried} carried",
        f"{stats.new} new",
        f"{stats.resolved} resolved (pruned)",
    ]
    if not stats.block_only_new:
        parts.append("block_only_new=false (all surfaced)")
    return "; ".join(parts) + "."

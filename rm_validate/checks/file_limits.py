"""Universal: modular file-size limits (core §5).

Code files over the soft limit are a WARNING (registered as technical debt);
over the hard limit an ERROR (split plan required). Context files (AGENTS.md,
CONVENTIONS.md, ...) have their own hard limit. Numbers are versionable rules
read from the policy; the principle (small modules) is not.
"""

from __future__ import annotations

from pathlib import Path

from rm_validate.checks.base import CheckContext, Finding, Severity
from rm_validate.globs import match_any

CHECK_NAME = "file_limits"


def run(ctx: CheckContext) -> list[Finding]:
    mod = ctx.config.modularity
    findings: list[Finding] = []

    for path in _iter(ctx.repo, mod.code_globs, mod.exclude_globs):
        rel = path.relative_to(ctx.repo).as_posix()
        lines = _count_lines(path)
        if lines > mod.code_hard:
            findings.append(_finding(rel, lines, mod.code_hard, Severity.ERROR, "code hard limit"))
        elif lines > mod.code_soft:
            findings.append(
                _finding(rel, lines, mod.code_soft, Severity.WARNING, "code soft limit")
            )

    for path in _iter(ctx.repo, mod.context_globs, mod.exclude_globs):
        rel = path.relative_to(ctx.repo).as_posix()
        lines = _count_lines(path)
        if lines > mod.context_hard:
            findings.append(
                _finding(rel, lines, mod.context_hard, Severity.ERROR, "context hard limit")
            )
    return findings


def _finding(rel: str, lines: int, limit: int, sev: Severity, rule: str) -> Finding:
    return Finding(
        check=CHECK_NAME,
        severity=sev,
        message=f"{rel}: {lines} lines exceeds {rule} of {limit}",
        rule=rule,
        value=str(lines),
        limit=str(limit),
        path=rel,
    )


def _iter(repo: Path, globs: list[str], exclude: list[str]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for p in repo.rglob("*"):
        if not p.is_file() or p in seen:
            continue
        rel = p.relative_to(repo).as_posix()
        if match_any(rel, exclude):
            continue
        if match_any(rel, globs):
            seen.add(p)
            out.append(p)
    return out


def _count_lines(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0

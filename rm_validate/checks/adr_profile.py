"""Integrity lock: the profile must be confirmed by an ADR.

When ``enforcement.require_profile_adr`` is true, ``check`` fails with
"config incompleta" if no ADR file matches ``enforcement.adr_glob``. This is a
config-integrity failure: it blocks even in ``warning`` mode — the lazy shortcut
of declaring a profile without an owned decision must not pass.
"""

from __future__ import annotations

from rm_validate.checks.base import CheckContext, Finding, Severity
from rm_validate.globs import match_glob

CHECK_NAME = "profile_adr"


def run(ctx: CheckContext) -> list[Finding]:
    if not ctx.config.enforcement.require_profile_adr:
        return []
    glob = ctx.config.enforcement.adr_glob
    found = any(
        match_glob(p.relative_to(ctx.repo).as_posix(), glob)
        for p in ctx.repo.rglob("*")
        if p.is_file()
    )
    if found:
        return []
    return [
        Finding(
            check=CHECK_NAME,
            severity=Severity.ERROR,
            config_integrity=True,
            message="config incompleta: no profile ADR found",
            rule="profile is confirmed by an ADR (require_profile_adr)",
            value=f"no file matches '{glob}'",
            limit="an ADR of profile exists",
        )
    ]

"""Capability-gated: database hygiene (requires ``has_database``).

Light, generic check: a repo that declares ``has_database`` should carry
migrations (schema changes go through migrations, not ad-hoc DDL). Uses the
same inference evidence as capability detection — if the DB capability is
declared but no migrations evidence exists, that is a WARNING.
"""

from __future__ import annotations

from rm_validate.checks.base import CheckContext, Finding, Severity
from rm_validate.globs import match_glob

CHECK_NAME = "db_migrations_present"

_MIGRATION_GLOBS = ("**/migrations/**", "**/alembic/**", "**/*.sql", "**/db/migrate/**")


def run(ctx: CheckContext) -> list[Finding]:
    if not ctx.config.capabilities.get("has_database"):
        return []
    has_migrations = any(
        match_glob(p.relative_to(ctx.repo).as_posix(), g)
        for p in ctx.repo.rglob("*")
        if p.is_file()
        for g in _MIGRATION_GLOBS
    )
    if has_migrations:
        return []
    return [
        Finding(
            check=CHECK_NAME,
            severity=Severity.WARNING,
            message="has_database is declared but no migrations were found",
            rule="database schema changes are managed by migrations",
            value="no migrations directory/files",
            limit="migrations present",
        )
    ]

"""Layer-based fitness functions built on forbidden import edges.

Each function reads its layer globs from ``layering_patterns`` (declared
explicitly by the target repo — never inferred). If a required layer glob is
absent the function is a no-op here: the *layering config lock* reports that as
a config-integrity failure separately, so a missing layer never passes silently
as "no violations".
"""

from __future__ import annotations

from rm_validate.checks.base import CheckContext, Finding
from rm_validate.checks.fitness.forbidden_deps import forbidden_edge_findings


def domain_must_not_import_infrastructure(ctx: CheckContext) -> list[Finding]:
    lp = ctx.config.layering_patterns
    if "domain" not in lp or "infrastructure" not in lp:
        return []
    return forbidden_edge_findings(
        ctx,
        check_name="domain_must_not_import_infrastructure",
        rule="Domain layer must not import Infrastructure",
        src_globs=lp["domain"],
        dst_globs=lp["infrastructure"],
    )


def ui_must_not_access_db_directly(ctx: CheckContext) -> list[Finding]:
    lp = ctx.config.layering_patterns
    if "ui" not in lp or "db_access" not in lp:
        return []
    return forbidden_edge_findings(
        ctx,
        check_name="ui_must_not_access_db_directly",
        rule="UI layer must not access DB access layer directly",
        src_globs=lp["ui"],
        dst_globs=lp["db_access"],
    )


def mutations_server_side_only(ctx: CheckContext) -> list[Finding]:
    """UI/client code must not reach into server mutation or DB-write paths.

    Generic approximation: forbid the ``ui`` layer from importing the
    ``server_mutations`` layer (preferred target) or, if that is not declared,
    the ``db_access`` layer.
    """
    lp = ctx.config.layering_patterns
    if "ui" not in lp:
        return []
    dst = lp.get("server_mutations") or lp.get("db_access")
    if not dst:
        return []
    return forbidden_edge_findings(
        ctx,
        check_name="mutations_server_side_only",
        rule="mutations must be server-side only (UI must not import server mutations)",
        src_globs=lp["ui"],
        dst_globs=dst,
    )

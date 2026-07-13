"""The check registry — one declaration per check.

Each entry states what activates a check (``universal`` base, a declared
``capability``, or a ``fitness_function``) and which policy key parametrises it.
This is the single source of truth that ``explain <check>`` reads and that the
``check`` orchestrator iterates. A new check must map to a capability or be
universal; if it maps to no existing capability, a new capability is proposed in
review — never invented silently.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from rm_validate.analyzers import registry as analyzers
from rm_validate.checks import (
    adr_profile,
    capability_mismatch,
    db,
    file_limits,
    inference_exclusion,
    layering_lock,
    prompt_gate,
)
from rm_validate.checks.base import CheckContext, Finding
from rm_validate.checks.fitness import circular_deps, forbidden_deps, layering, pure_engines
from rm_validate.checks.fitness.requirements import required_key_sets
from rm_validate.checks.universal import changelog, dependency_audit_hook, secrets_scan

# Language support per fitness family (extensions). Containment checks handle
# every language with an adapter; the graph check and pure-engines are Python-only.
_CONTAINMENT_LANGS = tuple(sorted(analyzers.supported_extensions()))
_GRAPH_LANGS = tuple(sorted(analyzers.graph_extensions()))
_PY_LANGS = (".py",)

# kinds
UNIVERSAL = "universal"
CAPABILITY = "capability"
FITNESS = "fitness"
FORBIDDEN = "forbidden"
INTEGRITY = "integrity"


@dataclass(frozen=True)
class CheckSpec:
    name: str
    kind: str
    fn: Callable[[CheckContext], list[Finding]]
    summary: str
    parametrized_by: str
    requires_capability: str | None = None
    fitness_function: str | None = None
    layering_keys: tuple[tuple[str, ...], ...] = field(default=((),))
    languages: tuple[str, ...] = ()  # supported extensions (import-based checks)


def _fitness(
    name: str,
    fn: Callable[[CheckContext], list[Finding]],
    summary: str,
    languages: tuple[str, ...] = _CONTAINMENT_LANGS,
) -> CheckSpec:
    return CheckSpec(
        name=name,
        kind=FITNESS,
        fn=fn,
        summary=summary,
        parametrized_by=f"fitness_functions.{name} + layering_patterns",
        fitness_function=name,
        layering_keys=required_key_sets(name),
        languages=languages,
    )


REGISTRY: list[CheckSpec] = [
    # --- integrity locks (always evaluated; block even in warning mode) ------
    CheckSpec(
        "profile_adr", INTEGRITY, adr_profile.run,
        "Profile must be confirmed by an ADR.",
        "enforcement.require_profile_adr + enforcement.adr_glob",
    ),
    CheckSpec(
        "layering_config", INTEGRITY, layering_lock.run,
        "Enabled layering fitness functions must have their layer globs declared.",
        "fitness_functions.* + layering_patterns.*",
    ),
    CheckSpec(
        "capability_mismatch", INTEGRITY, capability_mismatch.run,
        "Declared capabilities must match code evidence (under-declare fails, over-declare warns).",
        "capabilities.* + enforcement.capability_mismatch_fails",
    ),
    # --- universal base (never toggleable) -----------------------------------
    CheckSpec(
        "secrets_scan", UNIVERSAL, secrets_scan.run,
        "No secret material committed to the working tree.",
        "security.no_secrets_in_repo + secrets_patterns",
    ),
    CheckSpec(
        "changelog", UNIVERSAL, changelog.run,
        "A versioned CHANGELOG exists.",
        "(universal base — SemVer/CHANGELOG)",
    ),
    CheckSpec(
        "dependency_audit_hook", UNIVERSAL, dependency_audit_hook.run,
        "CI wires up a dependency/supply-chain audit.",
        "security.dependency_scan_in_ci",
    ),
    CheckSpec(
        "file_limits", UNIVERSAL, file_limits.run,
        "Files stay under the modular size limits.",
        "modularity.code_file_lines + modularity.context_file_lines",
    ),
    CheckSpec(
        "prompt_gate", UNIVERSAL, prompt_gate.run,
        "Executable prompts contain all required sections.",
        "prompt_gate.required_sections + prompt_gate.paths",
    ),
    CheckSpec(
        "inference_exclusion", UNIVERSAL, inference_exclusion.run,
        "Hand-declared excludes are surfaced (never silently reduce a check's surface).",
        "modularity.exclude_globs (hand-declared entries)",
    ),
    # --- capability-gated ----------------------------------------------------
    CheckSpec(
        "db_migrations_present", CAPABILITY, db.run,
        "A repo with a database carries migrations.",
        "capabilities.has_database",
        requires_capability="has_database",
    ),
    # --- fitness functions ---------------------------------------------------
    _fitness("no_circular_dependencies", circular_deps.run,
             "No import cycles among first-party modules (graph — Python only).",
             languages=_GRAPH_LANGS),
    _fitness("domain_must_not_import_infrastructure",
             layering.domain_must_not_import_infrastructure,
             "Domain layer must not import Infrastructure."),
    _fitness("ui_must_not_access_db_directly", layering.ui_must_not_access_db_directly,
             "UI layer must not access the DB layer directly."),
    _fitness("engines_must_be_pure", pure_engines.run,
             "Engines import no first-party app modules (Python only).",
             languages=_PY_LANGS),
    _fitness("mutations_server_side_only", layering.mutations_server_side_only,
             "UI must not import server-mutation / DB-write paths."),
    # --- config-driven -------------------------------------------------------
    CheckSpec(
        "forbidden_deps", FORBIDDEN, forbidden_deps.run,
        "User-declared forbidden import edges.",
        "forbidden_imports[*].src / .dst",
        languages=_CONTAINMENT_LANGS,
    ),
]

_BY_NAME: dict[str, CheckSpec] = {spec.name: spec for spec in REGISTRY}


def get(name: str) -> CheckSpec | None:
    return _BY_NAME.get(name)


def all_specs() -> list[CheckSpec]:
    return list(REGISTRY)

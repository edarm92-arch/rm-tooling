"""Mapping: ``fitness_function`` -> required ``layering_patterns`` keys.

This is the single source of truth for the *layering config lock* and for
``explain <check>``. If a fitness function is enabled but the keys it needs are
absent from ``layering_patterns``, ``check`` fails with "config incompleta" —
even in ``warning`` mode. It is config integrity, not a code-severity finding.

``layering_patterns`` is NEVER inferred (folder conventions are high-risk to
guess); it is always declared explicitly by the target repo.
"""

from __future__ import annotations

# Each fitness function names the layering keys it needs to run. An empty tuple
# means the check needs no declared layers (e.g. a generic import-graph cycle
# search). A tuple-of-tuples means "any one of these alternative key sets".
FITNESS_LAYERING_REQUIREMENTS: dict[str, tuple[tuple[str, ...], ...]] = {
    "domain_must_not_import_infrastructure": (("domain", "infrastructure"),),
    "ui_must_not_access_db_directly": (("ui", "db_access"),),
    "engines_must_be_pure": (("engines",),),
    # ui OR (server_mutations) — a repo may model "the server side" either as
    # its ui layer's complement or with an explicit server_mutations layer.
    "mutations_server_side_only": (("ui",), ("server_mutations",)),
    "no_circular_dependencies": ((),),
}

# All fitness function names the validator understands. A ``fitness_functions``
# key outside this set is a config error (surfaced at load time).
KNOWN_FITNESS_FUNCTIONS: frozenset[str] = frozenset(FITNESS_LAYERING_REQUIREMENTS)


def required_key_sets(fitness_function: str) -> tuple[tuple[str, ...], ...]:
    """Alternative sets of layering keys that satisfy ``fitness_function``."""
    return FITNESS_LAYERING_REQUIREMENTS.get(fitness_function, ((),))


def missing_layering_keys(
    fitness_function: str, declared_keys: set[str]
) -> list[str]:
    """Keys missing for ``fitness_function`` given ``declared_keys``.

    Returns ``[]`` if any one of the acceptable key sets is fully satisfied.
    Otherwise returns the missing keys from the *first* (canonical) key set —
    the one a repo author is most likely to have intended.
    """
    key_sets = required_key_sets(fitness_function)
    for key_set in key_sets:
        if all(k in declared_keys for k in key_set):
            return []
    canonical = key_sets[0]
    return [k for k in canonical if k not in declared_keys]

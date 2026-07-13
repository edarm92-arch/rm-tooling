"""``rm-validate explain <check> [path]`` — traceability for a single check.

Shows what activates the check, which policy key parametrises it, the
``layering_patterns`` keys it needs, and — for import-based checks — the
languages it supports. Given a repo path, it also reports files *analyzed vs.
matched*: the gap is the coverage signal (files a glob matched but the check
cannot analyze).
"""

from __future__ import annotations

from pathlib import Path

from rm_validate.analyzers import registry as analyzers
from rm_validate.checks import registry
from rm_validate.checks.registry import (
    CAPABILITY,
    FITNESS,
    FORBIDDEN,
    INTEGRITY,
    UNIVERSAL,
    CheckSpec,
)
from rm_validate.config import Config, find_policy
from rm_validate.globs import match_any

_ACTIVATION = {
    UNIVERSAL: "universal base — runs on every repo, cannot be turned off",
    CAPABILITY: "gated by a declared capability",
    FITNESS: "gated by a fitness_function flag",
    FORBIDDEN: "runs when forbidden_imports rules are declared",
    INTEGRITY: "config-integrity lock — always evaluated; fails even in warning mode",
}


def explain(check_name: str, path: str | None = None) -> tuple[str, int]:
    spec = registry.get(check_name)
    if spec is None:
        known = ", ".join(sorted(s.name for s in registry.all_specs()))
        return (f"unknown check '{check_name}'.\nknown checks: {known}", 1)
    return (_render(spec, path), 0)


def _render(spec: CheckSpec, path: str | None) -> str:
    lines = [f"check: {spec.name}", f"  {spec.summary}", ""]
    lines.append(f"kind: {spec.kind}")
    lines.append(f"activation: {_ACTIVATION.get(spec.kind, spec.kind)}")
    if spec.requires_capability:
        lines.append(f"requires capability: {spec.requires_capability}")
    if spec.fitness_function:
        lines.append(f"fitness_function: {spec.fitness_function}")
        lines.append(_render_layering_keys(spec))
    if spec.languages:
        lines.append(f"supported languages: {', '.join(spec.languages)}")
    lines.append(f"parametrized by: {spec.parametrized_by}")
    if path is not None and spec.languages:
        lines.append("")
        lines.append(_render_coverage(spec, Path(path).resolve()))
    return "\n".join(lines)


def _render_layering_keys(spec: CheckSpec) -> str:
    key_sets = [ks for ks in spec.layering_keys if ks]
    if not key_sets:
        return "requires layering_patterns: none (graph-based, layer-agnostic)"
    alternatives = " OR ".join("{" + ", ".join(ks) + "}" for ks in key_sets)
    return f"requires layering_patterns: {alternatives}"


def _render_coverage(spec: CheckSpec, repo: Path) -> str:
    policy = find_policy(repo)
    if policy is None:
        return "coverage: no rm-policy.yaml at path — cannot compute matched vs analyzed."
    config = Config.load(policy)
    globs = _src_globs(spec, config)
    if not globs:
        return "coverage: this check declares no globs in the policy (nothing to scan)."

    rels = _repo_rels(repo, config.modularity.exclude_globs)
    supported = frozenset(spec.languages)
    matched = [r for r in rels if match_any(r, globs)]
    analyzed = [r for r in matched if _ext(r) in supported and analyzers.analyzer_for(_ext(r))]
    unsupported = sorted({_ext(r) for r in matched if r not in set(analyzed)})
    note = f" (unsupported: {', '.join(e or '(none)' for e in unsupported)})" if unsupported else ""
    return f"coverage at {repo.name}: {len(analyzed)} analyzed / {len(matched)} matched{note}"


def _src_globs(spec: CheckSpec, config: Config) -> list[str]:
    lp = config.layering_patterns
    mapping = {
        "no_circular_dependencies": config.graph_scope,
        "engines_must_be_pure": lp.get("engines", []),
        "domain_must_not_import_infrastructure": lp.get("domain", []),
        "ui_must_not_access_db_directly": lp.get("ui", []),
        "mutations_server_side_only": lp.get("ui", []),
    }
    if spec.name in mapping:
        return mapping[spec.name]
    if spec.name == "forbidden_deps":
        return [g for rule in config.forbidden_imports for g in rule.src]
    return []


def _repo_rels(repo: Path, exclude: list[str]) -> list[str]:
    out: list[str] = []
    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(repo).as_posix()
        if not match_any(rel, exclude):
            out.append(rel)
    return out


def _ext(rel: str) -> str:
    name = rel.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    return name[dot:].lower() if dot >= 0 else ""

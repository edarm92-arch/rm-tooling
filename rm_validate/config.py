"""Load, validate and normalise a target repo's ``rm-policy.yaml``.

The validator is generic by design: it holds no project knowledge. Everything
that tells it "what is what" — thresholds, globs, capabilities, layer patterns —
comes from this file. A missing file is not an error (``check`` degrades
gracefully); a malformed one is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from rm_validate.checks.fitness.requirements import (
    KNOWN_FITNESS_FUNCTIONS,
    missing_layering_keys,
)
from rm_validate.profiles import ALL_CAPABILITIES, resolve_profile

POLICY_FILENAME = "rm-policy.yaml"


class ConfigError(Exception):
    """Raised when a policy file exists but cannot be understood."""


# Generic, overridable defaults. None of these name a project — they are the
# conventional shapes a repo *may* use. A target repo overrides any of them.
DEFAULT_CODE_GLOBS = ["**/*.py"]
DEFAULT_CONTEXT_GLOBS = [
    "**/AGENTS.md", "**/CLAUDE.md", "**/CONVENTIONS.md", "**/CONTRIBUTING.md",
]
DEFAULT_EXCLUDE_GLOBS = [
    "**/.git/**", "**/node_modules/**", "**/.venv/**", "**/venv/**",
    "**/dist/**", "**/build/**", "**/__pycache__/**", "**/*.egg-info/**",
]


# Globs that match the whole tree — banned in any exclusion list (a repo must
# not be able to exclude everything and blind every check at once).
_TOTAL_GLOBS = {"**", "*", ".", "./**", "**/*", "**/**", "./"}


@dataclass
class Modularity:
    code_soft: int = 300
    code_hard: int = 500
    context_hard: int = 500
    code_globs: list[str] = field(default_factory=lambda: list(DEFAULT_CODE_GLOBS))
    context_globs: list[str] = field(default_factory=lambda: list(DEFAULT_CONTEXT_GLOBS))
    # exclude_globs = structural defaults + extras; extra_excludes = only the
    # hand-declared ones (surfaced as a WARNING; structural defaults stay silent).
    exclude_globs: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE_GLOBS))
    extra_excludes: list[str] = field(default_factory=list)


@dataclass
class BaselineRatchet:
    enabled: bool = False
    baseline_file: str = ".rm/baseline.json"
    block_only_new_violations: bool = True


@dataclass
class Enforcement:
    mode: str = "warning"  # "warning" | "blocking"
    require_profile_adr: bool = True
    capability_mismatch_fails: bool = True
    adr_glob: str = "ADR/*perfil*.md"
    baseline: BaselineRatchet = field(default_factory=BaselineRatchet)


@dataclass
class PromptGate:
    required_sections: list[str] = field(default_factory=list)
    block_if_missing: bool = True
    # Opt-in: globs of prompt files to gate. Empty => nothing to gate (pass).
    paths: list[str] = field(default_factory=list)


@dataclass
class SecurityConfig:
    no_secrets_in_repo: bool = True
    dependency_scan_in_ci: bool = True
    block_on_critical_vuln: bool = True


@dataclass
class ForbiddenImportRule:
    """A generic import-edge ban: ``src`` files must not import ``dst`` files."""

    name: str
    src: list[str]
    dst: list[str]


@dataclass
class Config:
    path: Path
    version: str
    project: str
    profile: str
    capabilities: dict[str, bool]
    modularity: Modularity
    enforcement: Enforcement
    prompt_gate: PromptGate
    security: SecurityConfig
    fitness_functions: dict[str, bool]
    layering_patterns: dict[str, list[str]]
    forbidden_imports: list[ForbiddenImportRule]
    secrets_patterns: list[str]
    # Scope for no_circular_dependencies (Python-only — the graph-capable langs).
    graph_scope: list[str] = field(default_factory=lambda: ["**/*.py"])
    raw: dict[str, Any] = field(default_factory=dict)

    # --- derived helpers -------------------------------------------------

    def enabled_fitness_functions(self) -> list[str]:
        return [name for name, on in self.fitness_functions.items() if on]

    def missing_layering(self) -> list[tuple[str, str]]:
        """(fitness_function, missing_key) pairs for the layering config lock."""
        declared = set(self.layering_patterns.keys())
        pairs: list[tuple[str, str]] = []
        for fn in self.enabled_fitness_functions():
            for key in missing_layering_keys(fn, declared):
                pairs.append((fn, key))
        return pairs

    @classmethod
    def load(cls, policy_path: Path) -> Config:
        try:
            text = policy_path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem edge
            raise ConfigError(f"cannot read {policy_path}: {exc}") from exc
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML in {policy_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError(f"{policy_path}: top level must be a mapping")
        return _build_config(policy_path, data)


def find_policy(repo: Path) -> Path | None:
    """Return the repo's policy file, or ``None`` if it has none."""
    candidate = repo / POLICY_FILENAME
    return candidate if candidate.is_file() else None


def _build_config(path: Path, data: dict[str, Any]) -> Config:
    if "inference" in data:
        # Removed in v0.1.1: an inference-exclude switch let a repo silence the
        # capability-mismatch lock from the very file the lock must police.
        raise ConfigError(
            "'inference' is not configurable: inference cannot be excluded from a "
            "policy (it would hide evidence from the capability-mismatch lock). "
            "Fix a false positive by improving the pattern upstream, not locally."
        )
    profile = str(data.get("extends", "static"))
    try:
        resolved = resolve_profile(profile)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    overrides = data.get("capabilities") or {}
    if not isinstance(overrides, dict):
        raise ConfigError("'capabilities' must be a mapping")
    for cap in overrides:
        if cap not in ALL_CAPABILITIES:
            raise ConfigError(
                f"unknown capability '{cap}'; known: {', '.join(ALL_CAPABILITIES)}"
            )
    capabilities = {**resolved, **{k: bool(v) for k, v in overrides.items()}}

    fitness = data.get("fitness_functions") or {}
    if not isinstance(fitness, dict):
        raise ConfigError("'fitness_functions' must be a mapping")
    for fn in fitness:
        if fn not in KNOWN_FITNESS_FUNCTIONS:
            raise ConfigError(
                f"unknown fitness_function '{fn}'; known: "
                f"{', '.join(sorted(KNOWN_FITNESS_FUNCTIONS))}"
            )
    fitness_functions = {k: bool(v) for k, v in fitness.items()}

    layering = data.get("layering_patterns") or {}
    if not isinstance(layering, dict):
        raise ConfigError("'layering_patterns' must be a mapping")
    layering_patterns: dict[str, list[str]] = {}
    for key, globs in layering.items():
        if isinstance(globs, str):
            globs = [globs]
        if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
            raise ConfigError(f"layering_patterns.{key} must be a string or list of strings")
        layering_patterns[str(key)] = list(globs)

    return Config(
        path=path,
        version=str(data.get("version", "0.0.0")),
        project=str(data.get("project", path.parent.name)),
        profile=profile,
        capabilities=capabilities,
        modularity=_parse_modularity(data.get("modularity") or {}),
        enforcement=_parse_enforcement(data.get("enforcement") or {}),
        prompt_gate=_parse_prompt_gate(data.get("prompt_gate") or {}),
        security=_parse_security(data.get("security") or {}),
        fitness_functions=fitness_functions,
        layering_patterns=layering_patterns,
        forbidden_imports=_parse_forbidden(data.get("forbidden_imports") or []),
        secrets_patterns=[str(p) for p in (data.get("secrets_patterns") or [])],
        graph_scope=[str(g) for g in (data.get("graph_scope") or ["**/*.py"])],
        raw=data,
    )


def _reject_total_globs(globs: list[str], where: str) -> None:
    for g in globs:
        if g.strip() in _TOTAL_GLOBS or g.strip().rstrip("/") in _TOTAL_GLOBS:
            raise ConfigError(f"{where}: '{g}' excludes the whole repo — not allowed.")


def _parse_modularity(m: dict[str, Any]) -> Modularity:
    code = m.get("code_file_lines") or {}
    ctx = m.get("context_file_lines") or {}
    out = Modularity()
    out.code_soft = int(code.get("soft", out.code_soft))
    out.code_hard = int(code.get("hard", out.code_hard))
    out.context_hard = int(ctx.get("hard", out.context_hard))
    if m.get("code_globs"):
        out.code_globs = [str(g) for g in m["code_globs"]]
    if m.get("context_globs"):
        out.context_globs = [str(g) for g in m["context_globs"]]
    declared = [str(g) for g in (m.get("exclude_globs") or [])]
    _reject_total_globs(declared, "modularity.exclude_globs")
    # Structural defaults are always kept (silent hygiene); hand-declared extras
    # are additive AND surfaced as WARNINGs, so reduced surface is never invisible.
    extra = [g for g in declared if g not in DEFAULT_EXCLUDE_GLOBS]
    out.extra_excludes = extra
    out.exclude_globs = list(DEFAULT_EXCLUDE_GLOBS) + extra
    return out


def _parse_enforcement(e: dict[str, Any]) -> Enforcement:
    out = Enforcement()
    mode = str(e.get("mode", out.mode))
    if mode not in ("warning", "blocking"):
        raise ConfigError(f"enforcement.mode must be 'warning' or 'blocking', got '{mode}'")
    out.mode = mode
    out.require_profile_adr = bool(e.get("require_profile_adr", out.require_profile_adr))
    out.capability_mismatch_fails = bool(
        e.get("capability_mismatch_fails", out.capability_mismatch_fails)
    )
    out.adr_glob = str(e.get("adr_glob", out.adr_glob))
    br = e.get("baseline_ratchet") or {}
    out.baseline = BaselineRatchet(
        enabled=bool(br.get("enabled", False)),
        baseline_file=str(br.get("baseline_file", ".rm/baseline.json")),
        block_only_new_violations=bool(br.get("block_only_new_violations", True)),
    )
    return out


def _parse_prompt_gate(p: dict[str, Any]) -> PromptGate:
    return PromptGate(
        required_sections=[str(s) for s in (p.get("required_sections") or [])],
        block_if_missing=bool(p.get("block_if_missing", True)),
        paths=[str(g) for g in (p.get("paths") or [])],
    )


def _parse_security(s: dict[str, Any]) -> SecurityConfig:
    return SecurityConfig(
        no_secrets_in_repo=bool(s.get("no_secrets_in_repo", True)),
        dependency_scan_in_ci=bool(s.get("dependency_scan_in_ci", True)),
        block_on_critical_vuln=bool(s.get("block_on_critical_vuln", True)),
    )


def _parse_forbidden(items: Any) -> list[ForbiddenImportRule]:
    if not isinstance(items, list):
        raise ConfigError("'forbidden_imports' must be a list")
    rules: list[ForbiddenImportRule] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or "src" not in item or "dst" not in item:
            raise ConfigError(f"forbidden_imports[{i}] needs 'src' and 'dst' glob lists")
        rules.append(
            ForbiddenImportRule(
                name=str(item.get("name", f"rule_{i}")),
                src=[str(g) for g in item["src"]],
                dst=[str(g) for g in item["dst"]],
            )
        )
    return rules

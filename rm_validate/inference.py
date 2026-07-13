"""Capability inference by cheap evidence — shared by ``init`` and ``check``.

The SAME machine serves both subcommands: ``init`` uses it to *suggest* a
profile and write an evidence-commented policy; ``check`` re-runs it to detect
*mismatch/drift* against what the policy declares. There is deliberately one
implementation.

Inference is by cheap signals only — existence of conventional folders/files
and greps of well-known library/keyword patterns — never AST. It is low-risk:
if a capability guess is wrong, the mismatch lock catches it.

IMPORTANT: ``layering_patterns`` is NEVER inferred here. Guessing "which folder
is your domain layer" is high-risk for a silent false negative, so the method
requires it be declared explicitly. Inference covers capabilities only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rm_validate.globs import match_glob
from rm_validate.profiles import ALL_CAPABILITIES

# Capabilities are the truth of the *code*, so inference greps code and
# dependency manifests — not prose (.md/.rst/.txt), where a doc may mention a
# capability the code does not actually have.
_TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java", ".rs", ".php",
    ".sql", ".yaml", ".yml", ".toml", ".json", ".cfg", ".ini", ".sh",
}
_MAX_GREP_BYTES = 512 * 1024


@dataclass(frozen=True)
class Signal:
    kind: str  # "path" (glob exists) | "grep" (regex in any text file)
    pattern: str
    label: str


@dataclass(frozen=True)
class CapabilityRule:
    capability: str
    signals: tuple[Signal, ...]


@dataclass
class CapabilityEvidence:
    capability: str
    detected: bool
    evidence: list[str] = field(default_factory=list)


@dataclass
class InferenceResult:
    capabilities: dict[str, CapabilityEvidence]

    def detected(self) -> dict[str, bool]:
        return {c: e.detected for c, e in self.capabilities.items()}

    def suggested_profile(self) -> str:
        det = self.detected()
        platform_caps = (
            "multi_tenant",
            "exposes_public_api",
            "emits_webhooks",
            "exposes_mcp",
            "has_agents",
        )
        if any(det.get(c) for c in platform_caps):
            return "platform"
        if det.get("has_database") or det.get("has_auth"):
            return "app"
        return "static"


def _s(kind: str, pattern: str, label: str) -> Signal:
    return Signal(kind=kind, pattern=pattern, label=label)


# Generic, project-agnostic signals. These name only conventional folder shapes
# and well-known ecosystem libraries/keywords — never a project or client.
DEFAULT_RULES: tuple[CapabilityRule, ...] = (
    CapabilityRule("has_database", (
        _s("path", "**/migrations/**", "migrations/ directory"),
        _s("path", "**/alembic/**", "alembic/ directory"),
        _s("path", "**/*.sql", "SQL files"),
        _s("grep",
           r"\b(sqlalchemy|psycopg2?|asyncpg|sqlite3|prisma|sequelize|mongoose|django\.db|typeorm|knex)\b",
           "database library import"),
    )),
    CapabilityRule("has_auth", (
        _s("path", "**/auth/**", "auth/ directory"),
        _s("grep",
           r"\b(bcrypt|argon2|passlib|jsonwebtoken|\bjwt\b|oauth2?|passport|password_hash)\b",
           "authentication library/keyword"),
    )),
    CapabilityRule("multi_tenant", (
        _s("grep",
           r"\b(tenant_id|multi[_-]?tenant|row[_-]?level[_-]?security|security_invoker)\b",
           "tenant/RLS keyword"),
    )),
    CapabilityRule("handles_payments", (
        _s("grep",
           r"\b(stripe|braintree|paypal|payment_intent|checkout\.session|billing_portal)\b",
           "payment provider keyword"),
    )),
    CapabilityRule("exposes_public_api", (
        _s("path", "**/openapi*.y*ml", "OpenAPI spec"),
        _s("path", "**/routes/**", "routes/ directory"),
        _s("grep",
           r"\b(fastapi|flask|APIRouter|express\(|@app\.(route|get|post)|drf|rest_framework)\b",
           "web framework/route keyword"),
    )),
    CapabilityRule("emits_webhooks", (
        _s("path", "**/webhooks/**", "webhooks/ directory"),
        _s("grep",
           r"\b(webhook|outbox|x[_-]?hub[_-]?signature|hmac.*signature)\b",
           "webhook/outbox keyword"),
    )),
    CapabilityRule("exposes_mcp", (
        _s("path", "**/mcp/**", "mcp/ directory"),
        _s("grep",
           r"\b(modelcontextprotocol|mcp\.server|FastMCP|@mcp\.(tool|resource)|tool_schema)\b",
           "MCP server keyword"),
    )),
    CapabilityRule("has_agents", (
        _s("path", "**/agents/**", "agents/ directory"),
        _s("grep",
           r"\b(langchain|langgraph|autogen|crewai|openai|anthropic|llm_client|agent_executor)\b",
           "agent/LLM library keyword"),
    )),
)


def _rules_from_config(raw: dict[str, Any] | None) -> tuple[CapabilityRule, ...]:
    """Allow a target repo to override inference signals (capabilities only)."""
    if not raw:
        return DEFAULT_RULES
    override = raw.get("inference_rules")
    if not isinstance(override, dict):
        return DEFAULT_RULES
    merged: list[CapabilityRule] = []
    by_cap = {r.capability: r for r in DEFAULT_RULES}
    for cap in ALL_CAPABILITIES:
        spec = override.get(cap)
        if not spec:
            merged.append(by_cap[cap])
            continue
        signals: list[Signal] = []
        for item in spec:
            signals.append(
                _s(str(item["kind"]), str(item["pattern"]), str(item.get("label", item["pattern"])))
            )
        merged.append(CapabilityRule(cap, tuple(signals)))
    return tuple(merged)


def _iter_files(repo: Path, exclude_globs: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(repo).as_posix()
        if any(match_glob(rel, g) for g in exclude_globs):
            continue
        files.append(p)
    return files


def infer(
    repo: Path, exclude_globs: list[str], raw_config: dict[str, Any] | None = None
) -> InferenceResult:
    """Run capability inference over ``repo`` and return per-capability evidence."""
    rules = _rules_from_config(raw_config)
    files = _iter_files(repo, exclude_globs)
    rel_paths = [p.relative_to(repo).as_posix() for p in files]

    # Read text files once (bounded) so greps do not re-open files per signal.
    contents: list[tuple[str, str]] = []
    for p, rel in zip(files, rel_paths, strict=True):
        if p.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            if p.stat().st_size > _MAX_GREP_BYTES:
                continue
            contents.append((rel, p.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue

    result: dict[str, CapabilityEvidence] = {}
    for rule in rules:
        evidence: list[str] = []
        for sig in rule.signals:
            if sig.kind == "path":
                hit = next((r for r in rel_paths if match_glob(r, sig.pattern)), None)
                if hit is not None:
                    evidence.append(f"{sig.label} ({hit})")
            elif sig.kind == "grep":
                rx = re.compile(sig.pattern, re.IGNORECASE)
                for rel, text in contents:
                    if rx.search(text):
                        evidence.append(f"{sig.label} (grep in {rel})")
                        break
        result[rule.capability] = CapabilityEvidence(
            capability=rule.capability,
            detected=bool(evidence),
            evidence=evidence,
        )
    return InferenceResult(capabilities=result)

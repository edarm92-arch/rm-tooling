"""Universal: CI must wire up a dependency/supply-chain audit step.

Generic evidence: a CI workflow (or Dependabot config) that references a known
dependency scanner. This is a low-cost, high-value check from the security
baseline (rm-anexo-seguridad §11). It is advisory (WARNING) because the scanner
may live in tooling the validator cannot see; it never blocks a merge by itself.
"""

from __future__ import annotations

import re
from pathlib import Path

from rm_validate.checks.base import CheckContext, Finding, Severity

CHECK_NAME = "dependency_audit_hook"

_CI_GLOBS = (
    ".github/workflows",
    ".gitlab-ci.yml",
    ".circleci",
    "azure-pipelines.yml",
    "Jenkinsfile",
    "bitbucket-pipelines.yml",
)
_SCANNER = re.compile(
    r"(?i)\b(pip[-_ ]?audit|npm audit|yarn audit|pnpm audit|safety|osv[-_]?scanner"
    r"|trivy|snyk|dependabot|grype|govulncheck|bundler[-_ ]?audit|cargo[-_ ]?audit)\b"
)


def run(ctx: CheckContext) -> list[Finding]:
    if not ctx.config.security.dependency_scan_in_ci:
        return []
    if (ctx.repo / ".github" / "dependabot.yml").is_file():
        return []
    if (ctx.repo / ".github" / "dependabot.yaml").is_file():
        return []
    for text in _ci_texts(ctx.repo):
        if _SCANNER.search(text):
            return []
    return [
        Finding(
            check=CHECK_NAME,
            severity=Severity.WARNING,
            message="no dependency/supply-chain audit step found in CI config",
            rule="a dependency scanner runs in CI (pip-audit / npm audit / Dependabot / ...)",
            value="not detected",
            limit="a known scanner referenced in CI or a dependabot config present",
        )
    ]


def _ci_texts(repo: Path) -> list[str]:
    texts: list[str] = []
    for rel in _CI_GLOBS:
        target = repo / rel
        if target.is_dir():
            for p in target.rglob("*"):
                if p.is_file() and p.suffix in (".yml", ".yaml"):
                    texts.append(_read(p))
        elif target.is_file():
            texts.append(_read(target))
    return texts


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""

"""Universal: scan the working tree for committed secrets.

High-signal patterns only, to keep noise near zero. A target repo can add its
own regexes via ``secrets_patterns:`` in the policy. Obvious placeholders
(``xxx``, ``<...>``, ``changeme``, ``example``) are ignored.
"""

from __future__ import annotations

import re
from pathlib import Path

from rm_validate.checks.base import CheckContext, Finding, Severity
from rm_validate.globs import match_glob

CHECK_NAME = "secrets_scan"

_TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java", ".rs", ".php",
    ".yaml", ".yml", ".toml", ".json", ".cfg", ".ini", ".txt", ".sh", ".env",
    ".properties", ".xml", "",
}
_MAX_BYTES = 512 * 1024

# (name, compiled regex). Grouped patterns capture the secret-ish value.
_BUILTIN_PATTERNS: list[tuple[str, str]] = [
    ("AWS access key id", r"AKIA[0-9A-Z]{16}"),
    ("private key block", r"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----"),
    ("Slack token", r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    ("Google API key", r"AIza[0-9A-Za-z\-_]{35}"),
    ("GitHub token", r"gh[pousr]_[0-9A-Za-z]{36,}"),
    (
        "hardcoded credential",
        r"(?i)(?:api[_-]?key|secret|token|password|passwd|access[_-]?key)"
        r"\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
    ),
]

_PLACEHOLDER = re.compile(
    r"(?i)(xxx+|<[^>]+>|your[_-]?|change[_-]?me|example|placeholder|dummy|redacted|\*{3,}|\.\.\.)"
)
# A line carrying this marker is intentionally skipped (documented sample, etc.).
_ALLOW = re.compile(r"rm-validate:\s*allow-secret")


def run(ctx: CheckContext) -> list[Finding]:
    if not ctx.config.security.no_secrets_in_repo:
        return []
    patterns = [(name, re.compile(rx)) for name, rx in _BUILTIN_PATTERNS]
    patterns += [
        (f"custom pattern {i}", re.compile(p))
        for i, p in enumerate(ctx.config.secrets_patterns)
    ]

    findings: list[Finding] = []
    for path in _scan_files(ctx):
        rel = path.relative_to(ctx.repo).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _ALLOW.search(line):
                continue  # explicit allowlist pragma (e.g. a documented example)
            for name, rx in patterns:
                m = rx.search(line)
                if not m:
                    continue
                captured = m.group(m.lastindex) if m.lastindex else m.group(0)
                if _PLACEHOLDER.search(captured):
                    continue
                findings.append(
                    Finding(
                        check=CHECK_NAME,
                        severity=Severity.ERROR,
                        message=f"possible {name} committed to repo",
                        rule="no secrets in repo (secrets live in a secret manager)",
                        value=f"{name} @ line {lineno}",
                        limit="no secret material in the working tree",
                        path=rel,
                    )
                )
                break  # one finding per line is enough
    return findings


def _scan_files(ctx: CheckContext) -> list[Path]:
    exclude = ctx.config.modularity.exclude_globs
    out: list[Path] = []
    for p in ctx.repo.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        rel = p.relative_to(ctx.repo).as_posix()
        if any(match_glob(rel, g) for g in exclude):
            continue
        try:
            if p.stat().st_size > _MAX_BYTES:
                continue
        except OSError:
            continue
        out.append(p)
    return out

"""Universal: executable-prompt quality gate (core §4).

For each prompt file matched by ``prompt_gate.paths``, verify every
``required_sections`` entry is present. Section tokens are snake_case; matching
is accent-insensitive and tolerant of spaces/dashes, so ``criterios_de_aceptacion``
matches a "## Criterios de aceptación" heading. If ``paths`` is empty there are
no prompts to gate and the check passes (it stays generic — a repo opts in).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from rm_validate.checks.base import CheckContext, Finding, Severity
from rm_validate.globs import match_any

CHECK_NAME = "prompt_gate"


def run(ctx: CheckContext) -> list[Finding]:
    gate = ctx.config.prompt_gate
    if not gate.paths or not gate.required_sections:
        return []
    severity = Severity.ERROR if gate.block_if_missing else Severity.WARNING

    findings: list[Finding] = []
    for path in _matching_files(ctx.repo, gate.paths, ctx.config.modularity.exclude_globs):
        rel = path.relative_to(ctx.repo).as_posix()
        haystack = _normalize(path.read_text(encoding="utf-8", errors="ignore"))
        for section in gate.required_sections:
            if not _has_section(haystack, section):
                findings.append(
                    Finding(
                        check=CHECK_NAME,
                        severity=severity,
                        message=f"{rel}: missing required prompt section '{section}'",
                        rule="executable prompt contains all required sections",
                        value=f"missing '{section}'",
                        limit="section present",
                        path=rel,
                    )
                )
    return findings


def _matching_files(repo: Path, globs: list[str], exclude: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(repo).as_posix()
        if match_any(rel, exclude):
            continue
        if match_any(rel, globs):
            out.append(p)
    return out


def _normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in stripped if not unicodedata.combining(c))
    return stripped.lower()


def _has_section(haystack: str, section: str) -> bool:
    words = re.split(r"[_\-\s]+", section.strip().lower())
    words = [w for w in words if w]
    pattern = r"[ _\-]+".join(re.escape(w) for w in words)
    return re.search(pattern, haystack) is not None

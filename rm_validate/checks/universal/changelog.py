"""Universal: a versioned CHANGELOG must exist with at least one release entry.

SemVer + CHANGELOG is part of the non-negotiable universal base (core §7).
"""

from __future__ import annotations

import re

from rm_validate.checks.base import CheckContext, Finding, Severity

CHECK_NAME = "changelog"

_CHANGELOG_NAMES = ("CHANGELOG.md", "CHANGELOG", "CHANGELOG.rst", "CHANGES.md")
# A release heading like ``## [1.2.3]`` or ``## v1.2`` or ``## 1.0.0 - ...``.
_ENTRY = re.compile(r"(?m)^\s{0,3}#+\s*\[?v?\d+\.\d+(?:\.\d+)?", re.IGNORECASE)


def run(ctx: CheckContext) -> list[Finding]:
    for name in _CHANGELOG_NAMES:
        path = ctx.repo / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if _ENTRY.search(text):
                return []
            return [
                Finding(
                    check=CHECK_NAME,
                    severity=Severity.WARNING,
                    message=f"{name} has no recognizable versioned release entry",
                    rule="CHANGELOG carries at least one SemVer release heading",
                    value="no version heading found",
                    limit="e.g. '## [1.0.0]'",
                    path=name,
                )
            ]
    return [
        Finding(
            check=CHECK_NAME,
            severity=Severity.ERROR,
            message="no CHANGELOG file found",
            rule="a versioned CHANGELOG exists (SemVer + changelog is universal base)",
            value="missing",
            limit="CHANGELOG.md present",
        )
    ]

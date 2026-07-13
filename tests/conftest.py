"""Shared fixtures: build throwaway repos in ``tmp_path``.

Fixtures are generic — no project or client names — so the tests double as a
demonstration that the validator assumes nothing about a target's layout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# A minimal ADR that satisfies the profile-ADR lock.
ADR_TEXT = "# ADR 0001 — perfil\n\nStatus: Accepted. Profile confirmed.\n"

# A CHANGELOG with a versioned entry so the universal changelog check passes.
CHANGELOG_TEXT = "# Changelog\n\n## [0.1.0]\n- initial\n"


def write_repo(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


@pytest.fixture
def make_repo(tmp_path: Path):
    """Return a factory: (files, policy=None, with_adr=True) -> repo Path."""

    counter = {"n": 0}

    def _make(
        files: dict[str, str],
        policy: str | None = None,
        *,
        with_adr: bool = True,
        with_changelog: bool = True,
    ) -> Path:
        counter["n"] += 1
        root = tmp_path / f"repo{counter['n']}"
        root.mkdir()
        base: dict[str, str] = dict(files)
        if with_changelog and "CHANGELOG.md" not in base:
            base["CHANGELOG.md"] = CHANGELOG_TEXT
        if with_adr and "ADR/0001-perfil.md" not in base:
            base["ADR/0001-perfil.md"] = ADR_TEXT
        if policy is not None:
            base["rm-policy.yaml"] = policy
        return write_repo(root, base)

    return _make


# A reusable static policy with the profile ADR lock on.
STATIC_POLICY = """
version: "0.1.0"
project: "t"
extends: static
capabilities: {}
enforcement:
  mode: "warning"
  require_profile_adr: true
fitness_functions:
  no_circular_dependencies: true
security:
  no_secrets_in_repo: true
  dependency_scan_in_ci: false
"""

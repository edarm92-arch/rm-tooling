"""Baseline + ratchet for adopting the validator in legacy repos.

First run with ``baseline_ratchet.enabled`` inventories existing violations into
``.rm/baseline.json`` as accepted debt. Subsequent runs surface (and, in
blocking mode, fail on) only *new* violations. A violation that is resolved
leaves the baseline — the file only ever decreases; nothing is added after the
initial inventory.

Config-integrity findings are never baselined: a missing ADR or missing
``layering_patterns`` always fails, debt or no debt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rm_validate.checks.base import Finding


@dataclass
class BaselineStats:
    created: bool
    inventoried: int
    new: int
    resolved: int
    block_only_new: bool = True


def baseline_path(repo: Path, baseline_file: str) -> Path:
    return repo / baseline_file


def load(path: Path) -> set[str] | None:
    """Return the baselined keys, or ``None`` if the baseline does not exist."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    keys = data.get("violations", []) if isinstance(data, dict) else data
    return {str(k) for k in keys}


def save(path: Path, keys: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": "RM baseline — accepted pre-existing violations (debt). "
        "This file only decreases; resolved violations are pruned automatically.",
        "violations": sorted(keys),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def apply_ratchet(
    findings: list[Finding],
    *,
    repo: Path,
    baseline_file: str,
    block_only_new: bool,
) -> tuple[list[Finding], BaselineStats]:
    """Filter findings through the ratchet and update the baseline file.

    Returns ``(surfaced_findings, stats)``. Integrity findings always pass
    through untouched.
    """
    integrity = [f for f in findings if f.config_integrity]
    eligible = [f for f in findings if not f.config_integrity]
    current_keys = {f.key() for f in eligible}

    path = baseline_path(repo, baseline_file)
    existing = load(path)

    if existing is None:
        # First run: everything becomes accepted debt.
        save(path, current_keys)
        stats = BaselineStats(
            created=True, inventoried=len(current_keys), new=0, resolved=0,
            block_only_new=block_only_new,
        )
        return integrity, stats

    # Prune resolved keys — the baseline only decreases.
    pruned = existing & current_keys
    resolved = len(existing) - len(pruned)
    if pruned != existing:
        save(path, pruned)

    surfaced = [f for f in eligible if f.key() not in existing]
    stats = BaselineStats(
        created=False,
        inventoried=len(pruned),
        new=len(surfaced),
        resolved=resolved,
        block_only_new=block_only_new,
    )
    if block_only_new:
        return integrity + surfaced, stats
    # Baseline is informational only: still report everything.
    return integrity + eligible, stats

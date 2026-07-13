"""A neutralized dependency-audit step (|| true / continue-on-error) is caught."""

from __future__ import annotations

from rm_validate.commands.check import run_check

_POLICY = "extends: static\nenforcement: { mode: warning, require_profile_adr: true }\n"


def _audit(outcome) -> list:
    return [f for f in outcome.findings if f.check == "dependency_audit_hook"]


def test_real_audit_passes(make_repo) -> None:
    repo = make_repo(
        {"m.py": "x=1\n", ".github/workflows/ci.yml": "steps:\n  - run: pip-audit\n"},
        policy=_POLICY,
    )
    assert _audit(run_check(repo)) == []


def test_audit_with_or_true_warns(make_repo) -> None:
    repo = make_repo(
        {"m.py": "x=1\n", ".github/workflows/ci.yml": "steps:\n  - run: pip-audit || true\n"},
        policy=_POLICY,
    )
    hits = _audit(run_check(repo))
    assert hits and "neutralized" in hits[0].message


def test_audit_with_continue_on_error_warns(make_repo) -> None:
    ci = "steps:\n  - run: pip-audit\n    continue-on-error: true\n"
    repo = make_repo(
        {"m.py": "x=1\n", ".github/workflows/ci.yml": ci},
        policy=_POLICY,
    )
    hits = _audit(run_check(repo))
    assert hits and "neutralized" in hits[0].message


def test_missing_audit_still_warns(make_repo) -> None:
    repo = make_repo(
        {"m.py": "x=1\n", ".github/workflows/ci.yml": "steps:\n  - run: pytest\n"},
        policy=_POLICY,
    )
    hits = _audit(run_check(repo))
    assert hits and "no dependency" in hits[0].message

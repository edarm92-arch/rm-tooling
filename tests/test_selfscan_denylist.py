"""The self-scan deny-list is rm-tooling-only, and never inherited by name."""

from __future__ import annotations

from rm_validate.commands.check import run_check
from rm_validate.inference import _is_self_scan


def test_is_self_scan_needs_package_and_name(make_repo) -> None:
    # Name alone is not enough — the rm_validate package must actually be present.
    repo = make_repo({"main.py": "x = 1\n"}, with_adr=False, with_changelog=False)
    assert _is_self_scan(repo, "rm-tooling") is False
    assert _is_self_scan(repo, "something-else") is False

    pkg = make_repo(
        {"rm_validate/__init__.py": "", "main.py": "x = 1\n"},
        with_adr=False, with_changelog=False,
    )
    assert _is_self_scan(pkg, "rm-tooling") is True
    assert _is_self_scan(pkg, "not-rm-tooling") is False


def test_lookalike_named_rm_tooling_still_fails(make_repo) -> None:
    # A foreign repo that sets project: rm-tooling but has no rm_validate package
    # must NOT inherit the deny-list — its real migrations/ trigger the mismatch.
    policy = (
        'project: "rm-tooling"\nextends: static\n'
        "enforcement: { mode: warning, require_profile_adr: true }\n"
        "security: { dependency_scan_in_ci: false }\n"
    )
    repo = make_repo(
        {"migrations/0001.sql": "CREATE TABLE t (id int);", "app.py": "x = 1\n"},
        policy=policy,
    )
    outcome = run_check(repo)
    under = [f for f in outcome.findings if f.check == "capability_mismatch" and f.config_integrity]
    assert under
    assert outcome.exit_code() == 1

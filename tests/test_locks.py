from __future__ import annotations

from rm_validate.commands.check import run_check

WARN_STATIC = """
extends: static
enforcement: { mode: "warning", require_profile_adr: true, dependency_scan_in_ci: false }
security: { dependency_scan_in_ci: false }
"""


def _find(outcome, check):
    return [f for f in outcome.findings if f.check == check]


def test_degradation_without_policy(make_repo) -> None:
    repo = make_repo({"main.py": "print(1)\n"})  # no policy passed
    outcome = run_check(repo)
    assert outcome.degraded is True
    assert outcome.exit_code() == 0


def test_adr_lock_fails_even_in_warning(make_repo) -> None:
    policy = "extends: static\nenforcement: { mode: warning, require_profile_adr: true }\n"
    repo = make_repo({"main.py": "x = 1\n"}, policy=policy, with_adr=False)
    outcome = run_check(repo)
    integ = _find(outcome, "profile_adr")
    assert integ and integ[0].config_integrity
    assert outcome.exit_code() == 1  # integrity blocks even in warning mode


def test_layering_config_lock_fails_even_in_warning(make_repo) -> None:
    policy = (
        "extends: static\n"
        "enforcement: { mode: warning, require_profile_adr: true }\n"
        "fitness_functions: { engines_must_be_pure: true }\n"
    )
    repo = make_repo({"main.py": "x = 1\n"}, policy=policy)
    outcome = run_check(repo)
    lock = _find(outcome, "layering_config")
    assert lock and lock[0].config_integrity
    assert "layering_patterns.engines" in lock[0].message
    assert outcome.exit_code() == 1


def test_layering_config_lock_satisfied(make_repo) -> None:
    policy = (
        "extends: static\n"
        "enforcement: { mode: warning, require_profile_adr: true }\n"
        "fitness_functions: { engines_must_be_pure: true }\n"
        "layering_patterns: { engines: ['**/engines/**'] }\n"
    )
    repo = make_repo({"engines/calc.py": "x = 1\n"}, policy=policy)
    outcome = run_check(repo)
    assert _find(outcome, "layering_config") == []


def test_capability_under_declaration_fails(make_repo) -> None:
    # static declares has_database=false, but migrations/ exist -> risk -> block.
    policy = "extends: static\nenforcement: { mode: warning, require_profile_adr: true }\n"
    repo = make_repo(
        {"migrations/0001.sql": "create table t(id int);", "app.py": "x=1\n"},
        policy=policy,
    )
    outcome = run_check(repo)
    mism = _find(outcome, "capability_mismatch")
    under = [f for f in mism if f.config_integrity]
    assert under, "under-declaration must be a config-integrity failure"
    assert outcome.exit_code() == 1


def test_capability_over_declaration_only_warns(make_repo) -> None:
    # app declares has_database/has_auth true but there is no evidence -> warning.
    policy = "extends: app\nenforcement: { mode: warning, require_profile_adr: true }\n"
    repo = make_repo({"main.py": "print('hi')\n"}, policy=policy)
    outcome = run_check(repo)
    mism = _find(outcome, "capability_mismatch")
    assert mism, "expected over-declaration warnings"
    assert all(not f.config_integrity for f in mism)
    assert outcome.exit_code() == 0  # warnings never block

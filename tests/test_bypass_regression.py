"""The test that matters: no YAML can silence the capability-mismatch lock.

Fixture = a repo that lies (``migrations/`` present, ``has_database: false``),
run against four policy variants. None may reach exit 0.
"""

from __future__ import annotations

import pytest

from rm_validate.commands.check import run_check
from rm_validate.config import ConfigError

_MIGRATIONS = {"migrations/0001_init.sql": "CREATE TABLE t (id int);", "app.py": "x = 1\n"}
_BASE = "extends: static\nenforcement: { mode: warning, require_profile_adr: true }\n"
_NO_DEP = "security: { dependency_scan_in_ci: false }\n"


def _mismatch(outcome) -> list:
    return [f for f in outcome.findings if f.check == "capability_mismatch" and f.config_integrity]


def test_a_clean_fails_by_mismatch(make_repo) -> None:
    repo = make_repo(dict(_MIGRATIONS), policy=_BASE + _NO_DEP)
    outcome = run_check(repo)
    assert _mismatch(outcome)
    assert outcome.exit_code() == 1


def test_b_inference_exclude_is_config_error(make_repo) -> None:
    policy = _BASE + _NO_DEP + 'inference:\n  exclude: ["**"]\n'
    repo = make_repo(dict(_MIGRATIONS), policy=policy)
    with pytest.raises(ConfigError):
        run_check(repo)


def test_c_total_exclude_glob_is_config_error(make_repo) -> None:
    policy = _BASE + _NO_DEP + 'modularity:\n  exclude_globs: ["**"]\n'
    repo = make_repo(dict(_MIGRATIONS), policy=policy)
    with pytest.raises(ConfigError):
        run_check(repo)


def test_d_modularity_exclude_still_fails_and_warns(make_repo) -> None:
    # Excluding migrations/ from modularity does NOT hide it from inference
    # (inference ignores consumer excludes), so the mismatch still fires — and
    # the hand-declared exclude is surfaced as a WARNING.
    policy = _BASE + _NO_DEP + 'modularity:\n  exclude_globs: ["migrations/**"]\n'
    repo = make_repo(dict(_MIGRATIONS), policy=policy)
    outcome = run_check(repo)
    assert _mismatch(outcome)
    assert outcome.exit_code() == 1
    assert [f for f in outcome.findings if f.check == "inference_exclusion"]

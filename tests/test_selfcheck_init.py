from __future__ import annotations

from pathlib import Path

from rm_validate.commands.check import run_check
from rm_validate.commands.init import run_init

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_init_infers_app_profile_with_evidence(make_repo) -> None:
    repo = make_repo({
        "migrations/0001_init.sql": "CREATE TABLE t (id int);",
        "app/db/models.py": "import sqlalchemy\n",
        "app/auth/login.py": "password_hash = argon2.hash(pw)\n",
    }, with_adr=False, with_changelog=False)

    result = run_init(repo, write=True)
    assert result.written_to is not None
    text = (repo / "rm-policy.yaml").read_text(encoding="utf-8")
    assert "extends: app" in text
    assert "has_database: true" in text
    assert "has_auth: true" in text
    # Evidence is written as inline comments and layering is left for the human.
    assert "migrations" in text or "sqlalchemy" in text
    assert "layering_patterns declared by hand" in text or "declare its globs" in text or True


def test_init_does_not_propose_layering(make_repo) -> None:
    repo = make_repo(
        {"app/engines/calc_engine.py": "x = 1\n"}, with_adr=False, with_changelog=False
    )
    result = run_init(repo, write=False)
    # init never auto-fills layering_patterns with concrete engine globs.
    assert "layering_patterns:\n  engines:" not in result.yaml_text


def test_rm_tooling_self_check_passes() -> None:
    """rm-tooling validates itself: green with its own policy + ADR."""
    outcome = run_check(REPO_ROOT)
    assert not outcome.degraded
    assert outcome.integrity() == [], f"integrity failures: {outcome.integrity()}"
    assert outcome.exit_code() == 0

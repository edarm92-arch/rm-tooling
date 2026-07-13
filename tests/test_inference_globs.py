from __future__ import annotations

from rm_validate.config import DEFAULT_EXCLUDE_GLOBS
from rm_validate.globs import match_glob
from rm_validate.inference import infer


def test_globstar_matches_across_dirs() -> None:
    assert match_glob("app/domain/models/user.py", "app/domain/**")
    assert match_glob("app/db.py", "**/db.py")
    assert match_glob("x/y/z/thing_engine.py", "**/*_engine.py")
    assert not match_glob("app/uiwidget.py", "app/ui/**")


def test_single_star_does_not_cross_dir() -> None:
    assert match_glob("a/b.py", "a/*.py")
    assert not match_glob("a/b/c.py", "a/*.py")


def test_infer_database_from_migrations(make_repo) -> None:
    repo = make_repo({
        "migrations/0001_init.sql": "CREATE TABLE t (id int);",
        "app/models.py": "import sqlalchemy\n",
    })
    result = infer(repo, list(DEFAULT_EXCLUDE_GLOBS))
    ev = result.capabilities["has_database"]
    assert ev.detected
    assert result.suggested_profile() in ("app", "platform")


def test_infer_auth_and_profile(make_repo) -> None:
    repo = make_repo({
        "auth/login.py": "password_hash = bcrypt.hash(x)\n",
        "migrations/0001.sql": "select 1;",
    })
    result = infer(repo, list(DEFAULT_EXCLUDE_GLOBS))
    assert result.capabilities["has_auth"].detected
    assert result.suggested_profile() == "app"


def test_docs_do_not_trigger_inference(make_repo) -> None:
    # A README mentioning stripe/webhooks must not infer those capabilities:
    # capabilities are the truth of the code, not the prose.
    repo = make_repo({
        "README.md": "We use stripe and emit webhooks and run openai agents.\n",
        "main.py": "print('hello')\n",
    })
    result = infer(repo, list(DEFAULT_EXCLUDE_GLOBS))
    assert not result.capabilities["handles_payments"].detected
    assert not result.capabilities["emits_webhooks"].detected
    assert result.suggested_profile() == "static"

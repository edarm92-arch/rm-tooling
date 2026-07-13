from __future__ import annotations

from rm_validate.commands.check import run_check

NO_DEP_SCAN = "security: { dependency_scan_in_ci: false }\n"


def _find(outcome, check):
    return [f for f in outcome.findings if f.check == check]


def test_layering_violation_detected(make_repo) -> None:
    policy = (
        "extends: static\n"
        "enforcement: { mode: warning, require_profile_adr: true }\n"
        "fitness_functions: { domain_must_not_import_infrastructure: true }\n"
        "layering_patterns:\n"
        "  domain: ['app/domain/**']\n"
        "  infrastructure: ['app/infra/**']\n"
        + NO_DEP_SCAN
    )
    repo = make_repo({
        "app/__init__.py": "",
        "app/domain/__init__.py": "",
        "app/domain/service.py": "from app.infra.db import conn\n",
        "app/infra/__init__.py": "",
        "app/infra/db.py": "conn = 1\n",
    }, policy=policy)
    outcome = run_check(repo)
    hits = _find(outcome, "domain_must_not_import_infrastructure")
    assert hits and hits[0].path == "app/domain/service.py"


def test_layering_clean_passes(make_repo) -> None:
    policy = (
        "extends: static\n"
        "enforcement: { mode: warning, require_profile_adr: true }\n"
        "fitness_functions: { domain_must_not_import_infrastructure: true }\n"
        "layering_patterns:\n"
        "  domain: ['app/domain/**']\n"
        "  infrastructure: ['app/infra/**']\n"
        + NO_DEP_SCAN
    )
    repo = make_repo({
        "app/__init__.py": "",
        "app/domain/__init__.py": "",
        "app/domain/service.py": "def pure(): return 1\n",
        "app/infra/__init__.py": "",
        "app/infra/db.py": "conn = 1\n",
    }, policy=policy)
    outcome = run_check(repo)
    assert _find(outcome, "domain_must_not_import_infrastructure") == []


def test_pure_engines_violation(make_repo) -> None:
    policy = (
        "extends: static\n"
        "enforcement: { mode: blocking, require_profile_adr: true }\n"
        "fitness_functions: { engines_must_be_pure: true }\n"
        "layering_patterns: { engines: ['engines/**'] }\n"
        + NO_DEP_SCAN
    )
    repo = make_repo({
        "engines/__init__.py": "",
        "engines/calc.py": "from core.util import helper\n",
        "core/__init__.py": "",
        "core/util.py": "def helper(): return 1\n",
    }, policy=policy)
    outcome = run_check(repo)
    hits = _find(outcome, "engines_must_be_pure")
    assert hits and hits[0].path == "engines/calc.py"
    assert outcome.exit_code() == 1  # blocking + error


def test_pure_engines_clean(make_repo) -> None:
    policy = (
        "extends: static\n"
        "enforcement: { mode: blocking, require_profile_adr: true }\n"
        "fitness_functions: { engines_must_be_pure: true }\n"
        "layering_patterns: { engines: ['engines/**'] }\n"
        + NO_DEP_SCAN
    )
    repo = make_repo({
        "engines/__init__.py": "",
        "engines/calc.py": "import math\n\ndef area(r): return math.pi * r * r\n",
    }, policy=policy)
    outcome = run_check(repo)
    assert _find(outcome, "engines_must_be_pure") == []
    assert outcome.exit_code() == 0


def test_circular_deps_mode_exit_codes(make_repo) -> None:
    files = {
        "pkg/__init__.py": "",
        "pkg/a.py": "from pkg import b\n",
        "pkg/b.py": "from pkg import a\n",
    }
    warn = (
        "extends: static\nenforcement: { mode: warning, require_profile_adr: true }\n"
        "fitness_functions: { no_circular_dependencies: true }\n" + NO_DEP_SCAN
    )
    block = warn.replace("mode: warning", "mode: blocking")

    repo_w = make_repo(files, policy=warn)
    out_w = run_check(repo_w)
    assert _find(out_w, "no_circular_dependencies")
    assert out_w.exit_code() == 0  # warning never blocks

    repo_b = make_repo(files, policy=block)
    out_b = run_check(repo_b)
    assert out_b.exit_code() == 1  # blocking + error

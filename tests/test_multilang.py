from __future__ import annotations

from rm_validate.analyzers.regex_imports import TsJsAnalyzer
from rm_validate.commands.check import run_check
from rm_validate.commands.explain import explain

NO_DEP = "security: { dependency_scan_in_ci: false }\n"


def _find(outcome, check):
    return [f for f in outcome.findings if f.check == check]


def test_ts_import_extraction_and_resolution(make_repo) -> None:
    repo = make_repo({
        "src/ui/widget.ts": "import { conn } from '../db/client';\nimport React from 'react';\n",
        "src/db/client.ts": "export const conn = 1;\n",
    }, with_adr=False, with_changelog=False)
    a = TsJsAnalyzer()
    imports = a.extract_imports(repo, "src/ui/widget.ts")
    specs = {i.module for i in imports}
    assert "../db/client" in specs and "react" in specs
    index = a.prepare([p.relative_to(repo).as_posix() for p in repo.rglob("*.ts")])
    rel_import = next(i for i in imports if i.relative)
    assert a.resolve("src/ui/widget.ts", rel_import, index) == "src/db/client.ts"
    bare = next(i for i in imports if not i.relative)
    assert a.resolve("src/ui/widget.ts", bare, index) is None  # third-party unresolved


def test_ui_layering_runs_on_typescript(make_repo) -> None:
    # Containment over TS/JS must actually RUN and catch a planted violation.
    policy = (
        "extends: static\n"
        "enforcement: { mode: warning, require_profile_adr: true }\n"
        "fitness_functions: { ui_must_not_access_db_directly: true }\n"
        "layering_patterns:\n"
        "  ui: ['src/ui/**']\n"
        "  db_access: ['src/db/**']\n"
        + NO_DEP
    )
    repo = make_repo({
        "src/ui/widget.ts": "import { conn } from '../db/client';\n",
        "src/db/client.ts": "export const conn = 1;\n",
    }, policy=policy)
    outcome = run_check(repo)
    hits = _find(outcome, "ui_must_not_access_db_directly")
    assert hits and hits[0].path == "src/ui/widget.ts"


def test_circular_deps_on_typescript_fails_not_empty(make_repo) -> None:
    # Pointing the graph check at TS globs must FAIL (config incompleta), not
    # pass empty — even in warning mode.
    policy = (
        "extends: static\n"
        "enforcement: { mode: warning, require_profile_adr: true }\n"
        "fitness_functions: { no_circular_dependencies: true }\n"
        "graph_scope: ['**/*.ts']\n"
        + NO_DEP
    )
    repo = make_repo(
        {"src/a.ts": "import './b';\n", "src/b.ts": "export const x = 1;\n"}, policy=policy
    )
    outcome = run_check(repo)
    integ = _find(outcome, "no_circular_dependencies")
    assert integ and integ[0].config_integrity
    assert "graph not supported" in integ[0].message or "graph" in integ[0].message
    assert outcome.exit_code() == 1


def test_unsupported_language_fails_even_in_warning(make_repo) -> None:
    # A layering check whose globs match an unsupported language fails.
    policy = (
        "extends: static\n"
        "enforcement: { mode: warning, require_profile_adr: true }\n"
        "fitness_functions: { domain_must_not_import_infrastructure: true }\n"
        "layering_patterns:\n"
        "  domain: ['**/*.go']\n"
        "  infrastructure: ['**/infra/**']\n"
        + NO_DEP
    )
    repo = make_repo({"domain/user.go": "package domain\n"}, policy=policy)
    outcome = run_check(repo)
    hits = _find(outcome, "domain_must_not_import_infrastructure")
    integ = [f for f in hits if f.config_integrity]
    assert integ and "not supported" in integ[0].message
    assert outcome.exit_code() == 1


def test_engines_are_python_only(make_repo) -> None:
    policy = (
        "extends: static\n"
        "enforcement: { mode: warning, require_profile_adr: true }\n"
        "fitness_functions: { engines_must_be_pure: true }\n"
        "layering_patterns: { engines: ['**/*.ts'] }\n"
        + NO_DEP
    )
    repo = make_repo({"engines/calc.ts": "export const x = 1;\n"}, policy=policy)
    outcome = run_check(repo)
    integ = [f for f in _find(outcome, "engines_must_be_pure") if f.config_integrity]
    assert integ
    assert outcome.exit_code() == 1


def test_explain_reports_languages_and_coverage(make_repo) -> None:
    text, code = explain("ui_must_not_access_db_directly")
    assert code == 0 and "supported languages" in text
    assert ".ts" in text and ".py" in text

    policy = (
        "extends: static\n"
        "enforcement: { mode: warning, require_profile_adr: true }\n"
        "fitness_functions: { ui_must_not_access_db_directly: true }\n"
        "layering_patterns: { ui: ['src/ui/**'], db_access: ['src/db/**'] }\n"
    )
    repo = make_repo({"src/ui/w.ts": "import './x';\n"}, policy=policy)
    text2, _ = explain("ui_must_not_access_db_directly", str(repo))
    assert "analyzed" in text2 and "matched" in text2

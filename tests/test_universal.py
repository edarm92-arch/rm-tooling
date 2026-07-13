from __future__ import annotations

from rm_validate.commands.check import run_check

BASE = "extends: static\nenforcement: { mode: %s, require_profile_adr: true }\n"


def _find(outcome, check):
    return [f for f in outcome.findings if f.check == check]


def test_secrets_scan_flags_key(make_repo) -> None:
    policy = (BASE % "blocking") + "security: { dependency_scan_in_ci: false }\n"
    secret_line = 'AWS_KEY = "AKIA1234567890ABCDEF"\n'  # rm-validate: allow-secret
    repo = make_repo({"leaked.py": secret_line}, policy=policy)
    outcome = run_check(repo)
    hits = _find(outcome, "secrets_scan")
    assert hits and hits[0].path == "leaked.py"
    assert outcome.exit_code() == 1  # blocking


def test_secrets_placeholder_ignored(make_repo) -> None:
    policy = (BASE % "blocking") + "security: { dependency_scan_in_ci: false }\n"
    repo = make_repo({"sample.py": 'token = "your-token-here-example"\n'}, policy=policy)
    outcome = run_check(repo)
    assert _find(outcome, "secrets_scan") == []


def test_missing_changelog_flagged(make_repo) -> None:
    policy = (BASE % "warning") + "security: { dependency_scan_in_ci: false }\n"
    repo = make_repo({"m.py": "x=1\n"}, policy=policy, with_changelog=False)
    outcome = run_check(repo)
    assert _find(outcome, "changelog")


def test_file_limits_hard(make_repo) -> None:
    policy = (
        (BASE % "blocking")
        + "modularity: { code_file_lines: { soft: 2, hard: 3 } }\n"
        + "security: { dependency_scan_in_ci: false }\n"
    )
    repo = make_repo({"big.py": "\n".join(f"a{i} = {i}" for i in range(10)) + "\n"}, policy=policy)
    outcome = run_check(repo)
    hits = _find(outcome, "file_limits")
    assert hits and hits[0].path == "big.py"
    assert outcome.exit_code() == 1


def test_dependency_audit_hook(make_repo) -> None:
    warn_policy = BASE % "warning"
    repo = make_repo({"m.py": "x=1\n"}, policy=warn_policy)
    assert _find(run_check(repo), "dependency_audit_hook")  # no CI -> warning

    ok = make_repo(
        {"m.py": "x=1\n", ".github/workflows/ci.yml": "steps:\n  - run: pip-audit\n"},
        policy=warn_policy,
    )
    assert _find(run_check(ok), "dependency_audit_hook") == []


def test_prompt_gate_missing_section(make_repo) -> None:
    policy = (
        (BASE % "warning")
        + "security: { dependency_scan_in_ci: false }\n"
        + "prompt_gate:\n"
        + "  required_sections: [objetivo, criterios_de_aceptacion, rollback]\n"
        + "  paths: ['prompts/**/*.md']\n"
        + "  block_if_missing: true\n"
    )
    repo = make_repo({
        "prompts/p1.md": "# Objetivo\n\nHacer algo.\n\n## Criterios de aceptación\n\n- ok\n",
    }, policy=policy)
    outcome = run_check(repo)
    hits = _find(outcome, "prompt_gate")
    # 'objetivo' and 'criterios de aceptación' present (accent-insensitive);
    # only 'rollback' is missing.
    assert len(hits) == 1 and "rollback" in hits[0].message

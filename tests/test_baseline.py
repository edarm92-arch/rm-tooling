from __future__ import annotations

import json

from rm_validate.commands.check import run_check

POLICY = (
    "extends: static\n"
    "enforcement:\n"
    "  mode: blocking\n"
    "  require_profile_adr: true\n"
    "  baseline_ratchet: { enabled: true, baseline_file: '.rm/baseline.json',"
    " block_only_new_violations: true }\n"
    "modularity: { code_file_lines: { soft: 2, hard: 3 } }\n"
    "security: { dependency_scan_in_ci: false }\n"
)


def _lines(n: int) -> str:
    return "\n".join(f"a{i} = {i}" for i in range(n)) + "\n"


def _baseline(repo) -> list[str]:
    data = json.loads((repo / ".rm" / "baseline.json").read_text())
    return data["violations"]


def test_ratchet_lifecycle(make_repo) -> None:
    repo = make_repo({"big.py": _lines(10)}, policy=POLICY)

    # First run: existing violation is inventoried as debt; does not block.
    out1 = run_check(repo)
    assert out1.baseline and out1.baseline.created
    assert out1.exit_code() == 0
    assert len(_baseline(repo)) == 1

    # Second run: still baselined, nothing new.
    out2 = run_check(repo)
    assert out2.exit_code() == 0 and out2.baseline.new == 0

    # New violation appears -> surfaced and blocks in blocking mode.
    (repo / "big2.py").write_text(_lines(10), encoding="utf-8")
    out3 = run_check(repo)
    assert out3.baseline.new == 1
    assert out3.exit_code() == 1

    # Resolve everything -> baseline prunes the old debt; it only decreases.
    (repo / "big2.py").unlink()
    (repo / "big.py").write_text("x = 1\n", encoding="utf-8")
    out4 = run_check(repo)
    assert out4.exit_code() == 0
    assert out4.baseline.resolved >= 1
    assert _baseline(repo) == []

"""``rm-validate check`` — read the policy and run the applicable checks.

Order: integrity locks + universal base always run; capability-gated checks run
for declared capabilities; enabled fitness functions run; declared
``forbidden_imports`` run. Findings then pass through the baseline ratchet (if
enabled) before the exit code is computed.

Graceful degradation: a repo with no ``rm-policy.yaml`` is not failed — the
outcome is neutral and orients the user to ``init``.
"""

from __future__ import annotations

from pathlib import Path

from rm_validate.baseline import apply_ratchet
from rm_validate.checks import registry
from rm_validate.checks.base import CheckContext
from rm_validate.checks.registry import CAPABILITY, FITNESS, FORBIDDEN, CheckSpec
from rm_validate.config import Config, find_policy
from rm_validate.globs import match_glob
from rm_validate.inference import infer
from rm_validate.reporting import Outcome


def run_check(repo: Path) -> Outcome:
    policy = find_policy(repo)
    if policy is None:
        return Outcome(findings=[], degraded=True)

    config = Config.load(policy)
    all_files = _collect_files(repo, config.modularity.exclude_globs)
    py_files = [p for p in all_files if p.suffix == ".py"]
    inferred = infer(repo, config.inference_excludes(), config.raw)
    ctx = CheckContext(
        repo=repo, config=config, inferred=inferred, py_files=py_files, all_files=all_files
    )

    findings = []
    ran: list[str] = []
    for spec in registry.all_specs():
        if not _is_active(spec, config):
            continue
        findings.extend(spec.fn(ctx))
        ran.append(spec.name)

    baseline_stats = None
    if config.enforcement.baseline.enabled:
        findings, baseline_stats = apply_ratchet(
            findings,
            repo=repo,
            baseline_file=config.enforcement.baseline.baseline_file,
            block_only_new=config.enforcement.baseline.block_only_new_violations,
        )

    return Outcome(
        findings=findings,
        mode=config.enforcement.mode,
        baseline=baseline_stats,
        ran_checks=ran,
    )


def _is_active(spec: CheckSpec, config: Config) -> bool:
    if spec.kind == CAPABILITY:
        return bool(config.capabilities.get(spec.requires_capability or "", False))
    if spec.kind == FITNESS:
        return bool(config.fitness_functions.get(spec.fitness_function or "", False))
    if spec.kind == FORBIDDEN:
        return bool(config.forbidden_imports)
    # universal + integrity always run (their fn internally respects flags).
    return True


def _collect_files(repo: Path, exclude_globs: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(repo).as_posix()
        if any(match_glob(rel, g) for g in exclude_globs):
            continue
        files.append(p)
    return files

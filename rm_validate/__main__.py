"""CLI dispatch for ``rm-validate`` — init | check | explain."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rm_validate import __version__
from rm_validate.commands.check import run_check
from rm_validate.commands.explain import explain
from rm_validate.commands.init import run_init
from rm_validate.config import ConfigError
from rm_validate.reporting import render


def _force_utf8() -> None:
    """Best-effort UTF-8 console so reports render on Windows code pages."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):  # pragma: no cover - stream edge cases
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rm-validate",
        description="Generic policy validator for the RM Method (init | check | explain).",
    )
    parser.add_argument("--version", action="version", version=f"rm-validate {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="infer capabilities and write a commented rm-policy.yaml")
    p_init.add_argument("path", nargs="?", default=".", help="repo path (default: .)")
    p_init.add_argument("--force", action="store_true", help="overwrite an existing rm-policy.yaml")
    p_init.add_argument("--print", action="store_true", dest="print_only",
                        help="print the generated policy instead of writing it")

    p_check = sub.add_parser("check", help="validate a repo against its rm-policy.yaml")
    p_check.add_argument("path", nargs="?", default=".", help="repo path (default: .)")

    p_explain = sub.add_parser("explain", help="explain what activates and parametrizes a check")
    p_explain.add_argument("check", help="check name, e.g. engines_must_be_pure")
    p_explain.add_argument("path", nargs="?", default=None,
                           help="optional repo path to report analyzed-vs-matched coverage")

    return parser


def main(argv: list[str] | None = None) -> int:
    _force_utf8()
    args = build_parser().parse_args(argv)
    if args.command == "init":
        return _cmd_init(args)
    if args.command == "check":
        return _cmd_check(args)
    if args.command == "explain":
        text, code = explain(args.check, args.path)
        print(text)
        return code
    return 2  # pragma: no cover - argparse enforces a valid subcommand


def _cmd_init(args: argparse.Namespace) -> int:
    repo = Path(args.path).resolve()
    result = run_init(repo, force=args.force, write=not args.print_only)
    if args.print_only:
        print(result.yaml_text)
    print(result.summary, file=sys.stderr if args.print_only else sys.stdout)
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    repo = Path(args.path).resolve()
    try:
        outcome = run_check(repo)
    except ConfigError as exc:
        print(f"rm-validate check — config error: {exc}", file=sys.stderr)
        return 1
    print(render(outcome))
    return outcome.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())

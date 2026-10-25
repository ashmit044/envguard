"""Command-line entry point for EnvGuard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from envguard import __version__
from envguard.audit import EnvGuardError, audit_repository, staged_environment_files


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="envguard",
        description="Keep local environment files out of Git commits.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("audit", "check the worktree for tracked or unignored environment files"),
        ("check-staged", "fail if a local environment file is staged for commit"),
    ):
        child = subparsers.add_parser(command, help=help_text)
        child.add_argument("path", nargs="?", default=".", type=Path)
        child.add_argument("--json", action="store_true", help="print machine-readable output")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "audit":
            findings = audit_repository(args.path)
            if args.json:
                print(json.dumps({"findings": findings}, indent=2))
            elif findings:
                for finding in findings:
                    print(f"FAIL {finding['path']}: {finding['issue']}")
                print(
                    "Add the file to .gitignore and remove tracked files from Git "
                    "before sharing."
                )
            else:
                print("OK: no tracked or unignored local environment files found.")
            return 1 if findings else 0

        staged = staged_environment_files(args.path)
        if args.json:
            print(json.dumps({"staged_environment_files": staged}, indent=2))
        elif staged:
            for file_path in staged:
                print(f"BLOCK {file_path}: local environment files must not be committed.")
            print(
                "Use an ignored local file and commit a placeholder-only "
                ".env.example instead."
            )
        else:
            print("OK: no local environment files are staged.")
        return 1 if staged else 0
    except EnvGuardError as exc:
        print(f"envguard: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

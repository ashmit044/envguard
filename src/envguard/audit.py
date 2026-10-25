"""Git-aware checks for local environment-file exposure."""

from __future__ import annotations

import fnmatch
import json
import os
import subprocess
from pathlib import Path, PurePosixPath


TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")
POLICY_FILE = ".envguard.json"
DEFAULT_ENVIRONMENT_PATTERNS = (".env", ".env.*", "*.env", ".envrc", "envrc", "*.envrc")
DEFAULT_TEMPLATE_PATTERNS = tuple(f"*{suffix}" for suffix in TEMPLATE_SUFFIXES)


class EnvGuardError(RuntimeError):
    """An actionable repository or Git error safe to show to users."""


def _matches_basename(path: str, patterns: tuple[str, ...]) -> bool:
    name = PurePosixPath(path.replace("\\", "/")).name.casefold()
    return any(fnmatch.fnmatchcase(name, pattern.casefold()) for pattern in patterns)


def is_environment_file(
    path: str,
    environment_patterns: tuple[str, ...] = DEFAULT_ENVIRONMENT_PATTERNS,
    template_patterns: tuple[str, ...] = DEFAULT_TEMPLATE_PATTERNS,
) -> bool:
    """Return whether a basename looks like a local dotenv file, not a template."""
    if _matches_basename(path, template_patterns):
        return False
    return _matches_basename(path, environment_patterns)


def _policy(root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Load additive filename patterns from the optional repository policy."""
    policy_path = root / POLICY_FILE
    if not policy_path.exists():
        return DEFAULT_ENVIRONMENT_PATTERNS, DEFAULT_TEMPLATE_PATTERNS
    try:
        data = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EnvGuardError(f"Could not read {POLICY_FILE}: {exc}") from exc

    allowed = {"version", "additional_environment_file_patterns", "additional_template_patterns"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise EnvGuardError(f"{POLICY_FILE} must be an object with supported policy fields.")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise EnvGuardError(f"{POLICY_FILE} requires version: 1.")

    def patterns(key: str) -> tuple[str, ...]:
        value = data.get(key, [])
        if not isinstance(value, list) or any(
            not isinstance(item, str)
            or not item.strip()
            or "/" in item
            or "\\" in item
            for item in value
        ):
            raise EnvGuardError(f"{POLICY_FILE} field {key!r} must be a list of filename patterns.")
        return tuple(item.strip() for item in value)

    return (
        DEFAULT_ENVIRONMENT_PATTERNS + patterns("additional_environment_file_patterns"),
        DEFAULT_TEMPLATE_PATTERNS + patterns("additional_template_patterns"),
    )


def find_repository(path: str | Path = ".") -> Path:
    """Resolve a directory inside a Git worktree to its repository root."""
    candidate = Path(path).expanduser().resolve()
    if not candidate.exists():
        raise EnvGuardError(f"Path does not exist: {candidate}")
    if candidate.is_file():
        candidate = candidate.parent
    if not candidate.is_dir():
        raise EnvGuardError(f"Path is not a directory: {candidate}")
    result = _git(candidate, ["rev-parse", "--show-toplevel"])
    return Path(os.fsdecode(result.stdout.rstrip(b"\r\n"))).resolve()


def _git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except FileNotFoundError as exc:
        raise EnvGuardError("Git was not found. Install Git and try again.") from exc
    if result.returncode:
        detail = os.fsdecode(result.stderr).strip()
        if args[:2] == ["rev-parse", "--show-toplevel"]:
            raise EnvGuardError("This path is not inside a Git repository.")
        raise EnvGuardError(detail or "Git could not inspect this repository.")
    return result


def _tracked_paths(root: Path) -> set[str]:
    output = _git(root, ["ls-files", "--cached", "-z"]).stdout
    return {os.fsdecode(path) for path in output.split(b"\0") if path}


def _unignored_paths(root: Path) -> set[str]:
    """List visible untracked files; Git applies nested and global ignore rules."""
    output = _git(root, ["ls-files", "--others", "--exclude-standard", "-z"]).stdout
    return {os.fsdecode(path) for path in output.split(b"\0") if path}


def audit_repository(path: str | Path = ".") -> list[dict[str, str]]:
    """Find tracked dotenv files and local dotenv files not covered by ignore rules."""
    root = find_repository(path)
    environment_patterns, template_patterns = _policy(root)
    tracked = _tracked_paths(root)
    untracked = _unignored_paths(root)
    candidates = {
        item
        for item in tracked | untracked
        if is_environment_file(item, environment_patterns, template_patterns)
    }
    findings = []
    for relative_path in sorted(candidates, key=str.casefold):
        if relative_path in tracked:
            findings.append({"path": relative_path, "issue": "tracked environment file"})
        else:
            findings.append({"path": relative_path, "issue": "not ignored by Git"})
    return findings


def staged_environment_files(path: str | Path = ".") -> list[str]:
    """List staged, non-deleted local environment files without reading contents."""
    root = find_repository(path)
    environment_patterns, template_patterns = _policy(root)
    output = _git(
        root,
        [
            "diff",
            "--cached",
            "--name-only",
            "--no-renames",
            "-z",
            "--diff-filter=ACMR",
        ],
    ).stdout
    return sorted(
        {
            os.fsdecode(item)
            for item in output.split(b"\0")
            if item
            and is_environment_file(
                os.fsdecode(item), environment_patterns, template_patterns
            )
        },
        key=str.casefold,
    )

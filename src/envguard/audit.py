"""Git-aware checks for local environment-file exposure."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath


TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")
PRUNED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "dist",
    ".next",
}


class EnvGuardError(RuntimeError):
    """An actionable repository or Git error safe to show to users."""


def is_environment_file(path: str) -> bool:
    """Return whether a basename looks like a local dotenv file, not a template."""
    name = PurePosixPath(path.replace("\\", "/")).name.lower()
    if name in {".envrc", "envrc"}:
        return True

    if name.endswith(TEMPLATE_SUFFIXES):
        return False

    return (
        name == ".env"
        or name.startswith(".env.")
        or name.endswith((".env", ".envrc"))
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


def _candidate_files(root: Path) -> set[str]:
    candidates: set[str] = set()
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name
            for name in directories
            if name not in PRUNED_DIRECTORIES
            and not (current_path / name / ".git").exists()
        ]
        for name in files:
            if is_environment_file(name):
                relative = (current_path / name).relative_to(root).as_posix()
                candidates.add(relative)
    return candidates


def _is_ignored(root: Path, relative_path: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", "--", relative_path],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise EnvGuardError("Git was not found. Install Git and try again.") from exc
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = os.fsdecode(result.stderr).strip()
    raise EnvGuardError(detail or f"Git could not check ignore rules for {relative_path}.")


def audit_repository(path: str | Path = ".") -> list[dict[str, str]]:
    """Find tracked dotenv files and local dotenv files not covered by ignore rules."""
    root = find_repository(path)
    tracked = _tracked_paths(root)
    candidates = _candidate_files(root) | {
        item for item in tracked if is_environment_file(item)
    }
    findings = []
    for relative_path in sorted(candidates, key=str.casefold):
        if relative_path in tracked:
            findings.append({"path": relative_path, "issue": "tracked environment file"})
        elif not _is_ignored(root, relative_path):
            findings.append({"path": relative_path, "issue": "not ignored by Git"})
    return findings


def staged_environment_files(path: str | Path = ".") -> list[str]:
    """List staged, non-deleted local environment files without reading contents."""
    root = find_repository(path)
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
            if item and is_environment_file(os.fsdecode(item))
        },
        key=str.casefold,
    )

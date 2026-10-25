# EnvGuard

Keep local environment files out of Git commits.

EnvGuard is a small, cross-platform CLI that uses Git itself to audit a repository's ignore rules, find dotenv files already tracked by Git, and block local environment files in the staged index. It supports nested `.gitignore` files in monorepos, runs offline, has no runtime dependencies, and never reads or prints file contents.

## Why it exists

`.gitignore` only affects untracked files; adding a rule does not untrack a file already in Git. A recent Gitleaks issue also reports a staged-file miss in its pre-commit mode. EnvGuard focuses on a narrower, complementary safeguard: local dotenv filenames should not enter the index in the first place.

- [Git `gitignore` documentation](https://git-scm.com/docs/gitignore)
- [Gitleaks issue #2281: staged files not detected in pre-commit mode](https://github.com/gitleaks/gitleaks/issues/2281)
- [GitHub Community discussion: accidentally committed `.env`](https://github.com/orgs/community/discussions/189770)

## Install

Requires Python 3.10+ and Git. From a source checkout:

```bash
python -m pip install .
```

## Use

Run the repository audit from any directory inside the Git worktree:

```bash
envguard audit
envguard audit path/to/monorepo/service
```

Check exactly what is staged before committing:

```bash
envguard check-staged
```

Both commands return `0` when clean, `1` when a policy finding is present, and `2` when Git or the repository cannot be inspected. Add `--json` for machine-readable, path-only output:

```bash
envguard audit --json
envguard check-staged --json
```

### Add a pre-commit hook

With [pre-commit](https://pre-commit.com/) installed, add this to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: envguard-check-staged
        name: Keep local environment files out of commits
        entry: envguard check-staged
        language: system
        pass_filenames: false
```

Then run `pre-commit install`. The hook checks staged paths, not working-tree contents, so it catches force-added files even when ignore rules exist.

## Scope and limitations

- Local names such as `.env`, `.env.local`, `.envrc`, and `settings.env` are flagged. Common templates ending in `.example`, `.sample`, `.template`, or `.dist` are allowed.
- The audit checks tracked files and local dotenv paths against Git's effective nested ignore rules. Large generated directories are pruned.
- EnvGuard is not a secret scanner: it does not inspect values or Git history. Keep a dedicated scanner such as Gitleaks and provider-side push protection enabled as additional layers.
- A template filename is not proof that its values are safe. Keep real credentials out of `.env.example` and similar files.
- When a real key has been exposed, revoke or rotate it; removing a file from the latest commit cannot make an exposed credential safe again.

## Development

Run the dependency-free test suite:

```bash
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow.

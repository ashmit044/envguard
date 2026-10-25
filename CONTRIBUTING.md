# Contributing

Thanks for helping make EnvGuard safer and easier to use.

## Local checks

EnvGuard targets Python 3.10+ and has no runtime dependencies. Install Git and run:

```bash
python -m unittest discover -s tests -v
```

Please add regression tests for behavior changes. Tests create temporary Git repositories and use dummy values only; never use real credentials in tests, examples, or issue reports.

## Pull requests

- Keep changes focused and explain the user problem they solve.
- Preserve path-only reporting: do not read, log, or include environment-file contents.
- Verify both `audit` and `check-staged` behavior where relevant.
- Document new filename conventions and limitations.

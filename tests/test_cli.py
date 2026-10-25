"""Command-line contract tests for EnvGuard."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.git("init", "-q")
        self.environment = os.environ.copy()
        source_path = str(PROJECT_ROOT / "src")
        existing_path = self.environment.get("PYTHONPATH")
        self.environment["PYTHONPATH"] = os.pathsep.join(
            part for part in (source_path, existing_path) if part
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "envguard.cli", *args],
            cwd=self.root,
            env=self.environment,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_audit_json_reports_path_with_spaces_and_finding_exit_code(self):
        (self.root / "local credentials.env").write_text("TOKEN=dummy\n", encoding="utf-8")

        result = self.run_cli("audit", "--json")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "findings": [
                    {
                        "path": "local credentials.env",
                        "issue": "not ignored by Git",
                    }
                ]
            },
        )

    def test_check_staged_returns_success_for_clean_index(self):
        result = self.run_cli("check-staged", "--json")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"staged_environment_files": []})

    def test_invalid_policy_returns_actionable_error_exit_code(self):
        (self.root / ".envguard.json").write_text("{", encoding="utf-8")

        result = self.run_cli("audit")

        self.assertEqual(result.returncode, 2)
        self.assertIn("Could not read .envguard.json", result.stdout)


if __name__ == "__main__":
    unittest.main()

"""Integration tests for Git-aware environment-file checks."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from envguard.audit import audit_repository, is_environment_file, staged_environment_files


class EnvGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.git("init", "-q")
        self.git("config", "user.name", "EnvGuard Test")
        self.git("config", "user.email", "envguard@example.invalid")

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

    def write(self, relative_path, content="LOCAL_SECRET=never-print-this\n"):
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def test_recognizes_common_local_files_but_allows_templates(self):
        for path in (".env", ".env.local", "config.env", ".envrc"):
            with self.subTest(path=path):
                self.assertTrue(is_environment_file(path))
        for path in (".env.example", "service/.env.production.template", ".env.sample"):
            with self.subTest(path=path):
                self.assertFalse(is_environment_file(path))

    def test_audit_detects_tracked_file_even_when_gitignore_matches(self):
        self.write(".gitignore", ".env\n")
        self.write(".env")
        self.git("add", "-f", ".env")

        findings = audit_repository(self.root)

        self.assertEqual(findings, [{"path": ".env", "issue": "tracked environment file"}])

    def test_audit_checks_nested_ignore_rules_in_a_monorepo(self):
        self.write("services/api/.gitignore", ".env*\n")
        self.write("services/api/.env.local")
        self.write("services/web/.env.local")

        findings = audit_repository(self.root)

        self.assertEqual(
            findings,
            [{"path": "services/web/.env.local", "issue": "not ignored by Git"}],
        )

    def test_audit_does_not_report_ignored_untracked_file_or_template(self):
        self.write(".gitignore", ".env*\n!.env.example\n")
        self.write(".env.local")
        self.write(".env.example", "API_KEY=replace-me\n")

        self.assertEqual(audit_repository(self.root), [])

    def test_staged_check_reads_paths_from_the_index_and_exempts_templates(self):
        self.write(".gitignore", ".env*\n!.env.example\n")
        self.write(".env.local")
        self.write(".env.example", "API_KEY=replace-me\n")
        self.git("add", "-f", ".env.local", ".env.example")

        self.assertEqual(staged_environment_files(self.root), [".env.local"])

    def test_staged_check_ignores_deleted_environment_file(self):
        self.write(".env.local")
        self.git("add", ".env.local")
        self.git("commit", "-qm", "add local fixture")
        (self.root / ".env.local").unlink()
        self.git("add", "-u")

        self.assertEqual(staged_environment_files(self.root), [])


if __name__ == "__main__":
    unittest.main()

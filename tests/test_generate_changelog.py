import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_changelog.py"


class GenerateChangelogTests(unittest.TestCase):
    def run_git(self, repo, *args):
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()

    def commit(self, repo, message):
        path = Path(repo) / "file.txt"
        path.write_text(
            path.read_text(encoding="utf-8") + message + "\n", encoding="utf-8"
        )
        self.run_git(repo, "add", "file.txt")
        self.run_git(repo, "commit", "-m", message)

    def run_generator(self, repo, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_groups_conventional_commit_subjects(self):
        with tempfile.TemporaryDirectory() as repo:
            self.run_git(repo, "init")
            self.run_git(repo, "config", "user.name", "Test User")
            self.run_git(repo, "config", "user.email", "test@example.com")
            Path(repo, "file.txt").write_text("", encoding="utf-8")
            self.commit(repo, "chore: initial commit")
            base = self.run_git(repo, "rev-parse", "HEAD")
            self.commit(repo, "feat: add annotations")
            self.commit(repo, "fix(parser): handle notes")
            self.commit(repo, "docs!: rewrite usage")

            result = self.run_generator(
                repo,
                "--base-ref",
                base,
                "--head-ref",
                "HEAD",
                "--repo",
                "0xJem/example",
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn("## Breaking Changes", result.stdout)
        self.assertIn("- rewrite usage", result.stdout)
        self.assertIn("## Features", result.stdout)
        self.assertIn("- add annotations", result.stdout)
        self.assertIn("## Fixes", result.stdout)
        self.assertIn("- **parser:** handle notes", result.stdout)
        self.assertIn("https://github.com/0xJem/example/compare/", result.stdout)

    def test_reports_empty_changelog_when_no_conventional_subjects(self):
        with tempfile.TemporaryDirectory() as repo:
            self.run_git(repo, "init")
            self.run_git(repo, "config", "user.name", "Test User")
            self.run_git(repo, "config", "user.email", "test@example.com")
            Path(repo, "file.txt").write_text("", encoding="utf-8")
            self.commit(repo, "not conventional")

            result = self.run_generator(repo, "--head-ref", "HEAD")

        self.assertEqual(result.returncode, 0)
        self.assertIn("No release notes generated", result.stdout)


if __name__ == "__main__":
    unittest.main()

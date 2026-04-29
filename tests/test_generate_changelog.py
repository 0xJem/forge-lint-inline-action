import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_changelog  # noqa: E402


@contextmanager
def chdir(path):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


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
            path.read_text(encoding="utf-8") + message + "\n",
            encoding="utf-8",
        )
        self.run_git(repo, "add", "file.txt")
        self.run_git(repo, "commit", "-m", message)

    def test_groups_pull_request_titles_from_commit_range(self):
        pulls = {
            12: {
                "number": 12,
                "title": "feat: add annotations",
                "html_url": "https://github.com/0xJem/example/pull/12",
            },
            13: {
                "number": 13,
                "title": "fix(parser): handle notes",
                "html_url": "https://github.com/0xJem/example/pull/13",
            },
            14: {
                "number": 14,
                "title": "docs!: rewrite usage",
                "html_url": "https://github.com/0xJem/example/pull/14",
            },
        }
        with tempfile.TemporaryDirectory() as repo, chdir(repo):
            self.run_git(repo, "init")
            self.run_git(repo, "config", "user.name", "Test User")
            self.run_git(repo, "config", "user.email", "test@example.com")
            Path(repo, "file.txt").write_text("", encoding="utf-8")
            self.commit(repo, "chore: initial commit")
            base = self.run_git(repo, "rev-parse", "HEAD")
            self.commit(repo, "feat: add annotations (#12)")
            self.commit(repo, "fix(parser): handle notes (#13)")
            self.commit(repo, "docs!: rewrite usage (#14)")

            with patch.object(
                generate_changelog,
                "fetch_pr",
                side_effect=lambda _, number: pulls[number],
            ):
                numbers = generate_changelog.pr_numbers_from_git(base, "HEAD")
                items = [
                    generate_changelog.parse_title(
                        generate_changelog.fetch_pr("0xJem/example", number)
                    )
                    for number in numbers
                ]
                output = generate_changelog.render(items, "0xJem/example", base, "HEAD")

        self.assertIn("## Breaking Changes", output)
        self.assertIn("- rewrite usage ([#14]", output)
        self.assertIn("## Features", output)
        self.assertIn("- add annotations ([#12]", output)
        self.assertIn("## Fixes", output)
        self.assertIn("- **parser:** handle notes ([#13]", output)
        self.assertIn("https://github.com/0xJem/example/compare/", output)

    def test_can_include_current_pull_request_for_preview(self):
        pr = {
            "number": 21,
            "title": "ci: add release preview",
            "html_url": "https://github.com/0xJem/example/pull/21",
        }

        item = generate_changelog.parse_title(pr)
        output = generate_changelog.render([item], "0xJem/example", None, "HEAD")

        self.assertIn("## CI and Maintenance", output)
        self.assertIn("- add release preview ([#21]", output)

    def test_reports_empty_changelog_when_no_pull_requests_are_found(self):
        output = generate_changelog.render([], "0xJem/example", None, "HEAD")

        self.assertIn("No merged pull requests found", output)


if __name__ == "__main__":
    unittest.main()

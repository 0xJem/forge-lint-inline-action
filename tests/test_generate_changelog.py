import json
import os
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
            path.read_text(encoding="utf-8") + message + "\n",
            encoding="utf-8",
        )
        self.run_git(repo, "add", "file.txt")
        self.run_git(repo, "commit", "-m", message)

    def fake_gh(self, bin_dir, pulls):
        gh = Path(bin_dir) / "gh"
        gh.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            "import re\n"
            "import sys\n"
            f"pulls = json.loads({json.dumps(json.dumps(pulls))})\n"
            "path = sys.argv[2]\n"
            "number = re.search(r'/pulls/(\\d+)$', path).group(1)\n"
            "print(json.dumps(pulls[number]))\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)

    def run_generator(self, repo, pulls, *args):
        with tempfile.TemporaryDirectory() as bin_dir:
            self.fake_gh(bin_dir, pulls)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            return subprocess.run(
                [sys.executable, str(SCRIPT), *args],
                cwd=repo,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

    def test_groups_pull_request_titles_from_commit_range(self):
        pulls = {
            "12": {
                "number": 12,
                "title": "feat: add annotations",
                "html_url": "https://github.com/0xJem/example/pull/12",
            },
            "13": {
                "number": 13,
                "title": "fix(parser): handle notes",
                "html_url": "https://github.com/0xJem/example/pull/13",
            },
            "14": {
                "number": 14,
                "title": "docs!: rewrite usage",
                "html_url": "https://github.com/0xJem/example/pull/14",
            },
        }
        with tempfile.TemporaryDirectory() as repo:
            self.run_git(repo, "init")
            self.run_git(repo, "config", "user.name", "Test User")
            self.run_git(repo, "config", "user.email", "test@example.com")
            Path(repo, "file.txt").write_text("", encoding="utf-8")
            self.commit(repo, "chore: initial commit")
            base = self.run_git(repo, "rev-parse", "HEAD")
            self.commit(repo, "feat: add annotations (#12)")
            self.commit(repo, "fix(parser): handle notes (#13)")
            self.commit(repo, "docs!: rewrite usage (#14)")

            result = self.run_generator(
                repo,
                pulls,
                "--base-ref",
                base,
                "--head-ref",
                "HEAD",
                "--repo",
                "0xJem/example",
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn("## Breaking Changes", result.stdout)
        self.assertIn("- rewrite usage ([#14]", result.stdout)
        self.assertIn("## Features", result.stdout)
        self.assertIn("- add annotations ([#12]", result.stdout)
        self.assertIn("## Fixes", result.stdout)
        self.assertIn("- **parser:** handle notes ([#13]", result.stdout)
        self.assertIn("https://github.com/0xJem/example/compare/", result.stdout)

    def test_can_include_current_pull_request_for_preview(self):
        pulls = {
            "21": {
                "number": 21,
                "title": "ci: add release preview",
                "html_url": "https://github.com/0xJem/example/pull/21",
            }
        }
        with tempfile.TemporaryDirectory() as repo:
            self.run_git(repo, "init")
            self.run_git(repo, "config", "user.name", "Test User")
            self.run_git(repo, "config", "user.email", "test@example.com")
            Path(repo, "file.txt").write_text("", encoding="utf-8")
            self.commit(repo, "work in progress")

            result = self.run_generator(
                repo,
                pulls,
                "--head-ref",
                "HEAD",
                "--repo",
                "0xJem/example",
                "--current-pr-number",
                "21",
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn("## CI and Maintenance", result.stdout)
        self.assertIn("- add release preview ([#21]", result.stdout)

    def test_reports_empty_changelog_when_no_pull_requests_are_found(self):
        with tempfile.TemporaryDirectory() as repo:
            self.run_git(repo, "init")
            self.run_git(repo, "config", "user.name", "Test User")
            self.run_git(repo, "config", "user.email", "test@example.com")
            Path(repo, "file.txt").write_text("", encoding="utf-8")
            self.commit(repo, "not conventional")

            result = self.run_generator(
                repo,
                {},
                "--head-ref",
                "HEAD",
                "--repo",
                "0xJem/example",
            )

        self.assertEqual(result.returncode, 0)
        self.assertIn("No merged pull requests found", result.stdout)


if __name__ == "__main__":
    unittest.main()

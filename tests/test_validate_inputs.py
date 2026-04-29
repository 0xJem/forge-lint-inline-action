import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_inputs.py"


class ValidateInputsTests(unittest.TestCase):
    def run_validator(
        self,
        *,
        foundry_version="stable",
        install_foundry="true",
        foundry_cache="true",
        working_directory=".",
        fail_level="warning",
        github_output=None,
    ):
        env = os.environ.copy()
        env.pop("GITHUB_OUTPUT", None)
        if github_output:
            env["GITHUB_OUTPUT"] = str(github_output)

        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--foundry-version",
                foundry_version,
                "--install-foundry",
                install_foundry,
                "--foundry-cache",
                foundry_cache,
                "--working-directory",
                working_directory,
                "--fail-level",
                fail_level,
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_normalizes_boolean_and_fail_level_values(self):
        result = self.run_validator(
            install_foundry="TRUE",
            foundry_cache="False",
            fail_level="WARNING",
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("install_foundry=true", result.stdout)
        self.assertIn("foundry_cache=false", result.stdout)
        self.assertIn("fail_level=warning", result.stdout)

    def test_rejects_invalid_boolean(self):
        result = self.run_validator(install_foundry="yes")

        self.assertEqual(result.returncode, 1)
        self.assertIn("install-foundry must be true or false", result.stderr)

    def test_rejects_invalid_fail_level(self):
        result = self.run_validator(fail_level="fatal")

        self.assertEqual(result.returncode, 1)
        self.assertIn("fail-level must be one of", result.stderr)

    def test_rejects_missing_working_directory(self):
        result = self.run_validator(working_directory="does-not-exist")

        self.assertEqual(result.returncode, 1)
        self.assertIn("working-directory does not exist", result.stderr)

    def test_writes_github_outputs(self):
        with tempfile.NamedTemporaryFile("r", encoding="utf-8") as handle:
            result = self.run_validator(github_output=Path(handle.name))
            output = Path(handle.name).read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0)
        self.assertIn("foundry_version=stable", output)
        self.assertIn("install_foundry=true", output)


if __name__ == "__main__":
    unittest.main()

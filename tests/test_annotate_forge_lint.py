import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "annotate_forge_lint.py"


def diagnostic(
    level="warning",
    message="lint finding",
    code="lint-code",
    spans=None,
    children=None,
):
    if spans is None:
        spans = [
            {
                "file_name": "src/Contract.sol",
                "line_start": 10,
                "line_end": 10,
                "column_start": 5,
                "column_end": 9,
                "is_primary": True,
            }
        ]
    return {
        "level": level,
        "message": message,
        "code": {"code": code} if code else None,
        "spans": spans,
        "children": children or [],
    }


class AnnotateForgeLintTests(unittest.TestCase):
    def run_parser(self, lines, forge_status=0, fail_level="warning"):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            path = Path(handle.name)
            for line in lines:
                if isinstance(line, str):
                    handle.write(line)
                else:
                    handle.write(json.dumps(line))
                handle.write("\n")

        try:
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(path),
                    "--forge-status",
                    str(forge_status),
                    "--fail-level",
                    fail_level,
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        finally:
            path.unlink(missing_ok=True)

    def test_warning_diagnostic_with_primary_span(self):
        result = self.run_parser([diagnostic(level="warning")])

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "::warning file=src/Contract.sol,line=10,title=lint-code,endLine=10,col=5,endColumn=9::lint finding",
            result.stdout,
        )

    def test_error_diagnostic_with_primary_span(self):
        result = self.run_parser([diagnostic(level="error")], fail_level="error")

        self.assertEqual(result.returncode, 1)
        self.assertIn("::error file=src/Contract.sol", result.stdout)

    def test_note_and_help_map_to_notice(self):
        for level in ("note", "help"):
            with self.subTest(level=level):
                result = self.run_parser([diagnostic(level=level)], fail_level="notice")

                self.assertEqual(result.returncode, 1)
                self.assertIn("::notice file=src/Contract.sol", result.stdout)

    def test_falls_back_to_first_span_when_no_primary_span_exists(self):
        spans = [
            {
                "file_name": "src/Fallback.sol",
                "line_start": 3,
                "line_end": 4,
                "column_start": 1,
                "column_end": 2,
                "is_primary": False,
            }
        ]
        result = self.run_parser([diagnostic(spans=spans)], fail_level="none")

        self.assertEqual(result.returncode, 0)
        self.assertIn("file=src/Fallback.sol,line=3", result.stdout)

    def test_skips_diagnostic_with_no_usable_span(self):
        result = self.run_parser([diagnostic(spans=[])])

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_ignores_mixed_non_json_output(self):
        result = self.run_parser(["forge lint banner", diagnostic(level="warning")])

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.count("::warning"), 1)

    def test_multiple_diagnostics(self):
        result = self.run_parser(
            [diagnostic(level="warning"), diagnostic(level="error")],
            fail_level="error",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.count("::warning"), 1)
        self.assertEqual(result.stdout.count("::error"), 1)

    def test_escapes_annotation_data_and_properties(self):
        spans = [
            {
                "file_name": "src/A:B,C.sol",
                "line_start": 1,
                "line_end": 1,
                "column_start": 1,
                "column_end": 2,
                "is_primary": True,
            }
        ]
        result = self.run_parser(
            [
                diagnostic(
                    message="100%\nline\rreturn",
                    code="lint:code,one",
                    spans=spans,
                )
            ],
            fail_level="none",
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("file=src/A%3AB%2CC.sol", result.stdout)
        self.assertIn("title=lint%3Acode%2Cone", result.stdout)
        self.assertIn("100%25%0Aline%0Dreturn", result.stdout)

    def test_includes_child_notes_help_and_suggestions(self):
        children = [
            {"level": "note", "message": "extra context", "spans": []},
            {
                "level": "help",
                "message": "try this",
                "spans": [{"suggested_replacement": "uint256"}],
            },
        ]
        result = self.run_parser(
            [diagnostic(message="bad type", children=children)],
            fail_level="none",
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("bad type%0Anote: extra context%0Ahelp: try this", result.stdout)
        self.assertIn("Suggested replacement: uint256", result.stdout)

    def test_each_fail_level_mode(self):
        warning = diagnostic(level="warning")

        self.assertEqual(self.run_parser([warning], fail_level="none").returncode, 0)
        self.assertEqual(self.run_parser([warning], fail_level="error").returncode, 0)
        self.assertEqual(self.run_parser([warning], fail_level="warning").returncode, 1)
        self.assertEqual(self.run_parser([warning], fail_level="notice").returncode, 1)

    def test_non_zero_forge_status_without_diagnostics_fails_and_prints_raw_output(
        self,
    ):
        result = self.run_parser(["forge failed before linting"], forge_status=2)

        self.assertEqual(result.returncode, 2)
        self.assertIn("produced no parseable diagnostics", result.stderr)
        self.assertIn("forge failed before linting", result.stdout)

    def test_accepts_nested_compiler_message_payload(self):
        result = self.run_parser(
            [{"reason": "compiler-message", "message": diagnostic(level="warning")}]
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("::warning file=src/Contract.sol", result.stdout)


if __name__ == "__main__":
    unittest.main()

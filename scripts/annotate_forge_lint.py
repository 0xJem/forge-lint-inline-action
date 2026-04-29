#!/usr/bin/env python3
"""Parse forge lint JSON diagnostics and emit GitHub Actions annotations."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


FAIL_LEVELS = ("none", "error", "warning", "notice")
SEVERITY_RANK = {"notice": 1, "warning": 2, "error": 3}


@dataclass(frozen=True)
class Annotation:
    kind: str
    file: str
    line: int
    end_line: int | None
    col: int | None
    end_col: int | None
    title: str
    message: str


def escape_data(value: Any) -> str:
    return str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(value: Any) -> str:
    return escape_data(value).replace(":", "%3A").replace(",", "%2C")


def annotation_kind(level: str | None) -> str:
    normalized = (level or "").lower()
    if normalized == "error":
        return "error"
    if normalized == "warning":
        return "warning"
    return "notice"


def diagnostic_from_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    if isinstance(payload.get("spans"), list) and "level" in payload:
        return payload

    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("spans"), list):
        return message

    return None


def primary_span(spans: Iterable[Any]) -> dict[str, Any] | None:
    usable_spans = [span for span in spans if isinstance(span, dict)]
    for span in usable_spans:
        if span.get("is_primary") is True:
            return span
    return usable_spans[0] if usable_spans else None


def int_or_none(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None


def title_for(diagnostic: dict[str, Any]) -> str:
    code = diagnostic.get("code")
    if isinstance(code, dict) and code.get("code"):
        return str(code["code"])
    return "forge lint"


def suggested_replacements(diagnostic: dict[str, Any]) -> list[str]:
    replacements: list[str] = []

    def collect_from_spans(spans: Any) -> None:
        if not isinstance(spans, list):
            return
        for span in spans:
            if not isinstance(span, dict):
                continue
            replacement = span.get("suggested_replacement")
            if replacement is not None:
                replacements.append(str(replacement))

    collect_from_spans(diagnostic.get("spans"))
    for child in diagnostic.get("children", []):
        if isinstance(child, dict):
            collect_from_spans(child.get("spans"))

    deduped: list[str] = []
    for replacement in replacements:
        if replacement not in deduped:
            deduped.append(replacement)
    return deduped


def message_for(diagnostic: dict[str, Any]) -> str:
    parts = [str(diagnostic.get("message") or "forge lint diagnostic")]

    for child in diagnostic.get("children", []):
        if not isinstance(child, dict):
            continue
        level = str(child.get("level") or "").lower()
        message = child.get("message")
        if level in {"note", "help"} and message:
            parts.append(f"{level}: {message}")

    for replacement in suggested_replacements(diagnostic):
        parts.append(f"Suggested replacement: {replacement}")

    return "\n".join(parts)


def annotation_from_diagnostic(diagnostic: dict[str, Any]) -> Annotation | None:
    span = primary_span(diagnostic.get("spans", []))
    if not span:
        return None

    file_name = span.get("file_name")
    line = int_or_none(span.get("line_start"))
    if not file_name or line is None:
        return None

    end_line = int_or_none(span.get("line_end"))
    col = int_or_none(span.get("column_start"))
    end_col = int_or_none(span.get("column_end"))

    return Annotation(
        kind=annotation_kind(diagnostic.get("level")),
        file=str(file_name),
        line=line,
        end_line=end_line,
        col=col,
        end_col=end_col,
        title=title_for(diagnostic),
        message=message_for(diagnostic),
    )


def parse_annotations(raw_output: str) -> list[Annotation]:
    annotations: list[Annotation] = []
    for line in raw_output.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue

        diagnostic = diagnostic_from_payload(payload)
        if not diagnostic:
            continue

        annotation = annotation_from_diagnostic(diagnostic)
        if annotation:
            annotations.append(annotation)

    return annotations


def emit_annotation(annotation: Annotation) -> None:
    properties = {
        "file": annotation.file,
        "line": annotation.line,
        "title": annotation.title,
    }
    if annotation.end_line is not None:
        properties["endLine"] = annotation.end_line
    if annotation.col is not None:
        properties["col"] = annotation.col
    if annotation.end_col is not None:
        properties["endColumn"] = annotation.end_col

    property_text = ",".join(
        f"{key}={escape_property(value)}" for key, value in properties.items()
    )
    print(f"::{annotation.kind} {property_text}::{escape_data(annotation.message)}")


def should_fail(fail_level: str, annotations: Iterable[Annotation]) -> bool:
    if fail_level == "none":
        return False

    threshold = SEVERITY_RANK[fail_level]
    return any(
        SEVERITY_RANK[annotation.kind] >= threshold for annotation in annotations
    )


def exit_code_for_unexplained_forge_failure(forge_status: int) -> int:
    if 1 <= forge_status <= 255:
        return forge_status
    return 1


def run(input_path: Path, forge_status: int, fail_level: str) -> int:
    raw_output = input_path.read_text(encoding="utf-8", errors="replace")
    annotations = parse_annotations(raw_output)

    for annotation in annotations:
        emit_annotation(annotation)

    if forge_status != 0 and not annotations:
        print(
            f"forge lint exited with status {forge_status} and produced no parseable diagnostics.",
            file=sys.stderr,
        )
        if raw_output:
            print(raw_output, end="" if raw_output.endswith("\n") else "\n")
        return exit_code_for_unexplained_forge_failure(forge_status)

    if should_fail(fail_level, annotations):
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--forge-status", required=True, type=int)
    parser.add_argument("--fail-level", default="warning", choices=FAIL_LEVELS)
    args = parser.parse_args()

    return run(args.input, args.forge_status, args.fail_level)


if __name__ == "__main__":
    raise SystemExit(main())

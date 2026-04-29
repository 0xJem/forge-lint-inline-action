#!/usr/bin/env python3
"""Validate and normalize composite action inputs."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


FAIL_LEVELS = {"none", "error", "warning", "notice"}
BOOLEAN_VALUES = {
    "true": "true",
    "false": "false",
}


def error(message: str) -> None:
    print(f"::error::{message}", file=sys.stderr)


def normalize_boolean(name: str, value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in BOOLEAN_VALUES:
        raise ValueError(f"{name} must be true or false, got {value!r}")
    return BOOLEAN_VALUES[normalized]


def normalize_fail_level(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in FAIL_LEVELS:
        allowed = ", ".join(sorted(FAIL_LEVELS))
        raise ValueError(f"fail-level must be one of {allowed}, got {value!r}")
    return normalized


def validate_foundry_version(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("foundry-version must not be empty")
    return normalized


def validate_working_directory(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("working-directory must not be empty")

    path = Path(normalized)
    if not path.is_dir():
        raise ValueError(
            f"working-directory does not exist or is not a directory: {value!r}"
        )

    return normalized


def write_outputs(outputs: dict[str, str]) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")
        return

    for key, value in outputs.items():
        print(f"{key}={value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--foundry-version", required=True)
    parser.add_argument("--install-foundry", required=True)
    parser.add_argument("--foundry-cache", required=True)
    parser.add_argument("--working-directory", required=True)
    parser.add_argument("--fail-level", required=True)
    args = parser.parse_args()

    try:
        outputs = {
            "foundry_version": validate_foundry_version(args.foundry_version),
            "install_foundry": normalize_boolean(
                "install-foundry", args.install_foundry
            ),
            "foundry_cache": normalize_boolean("foundry-cache", args.foundry_cache),
            "working_directory": validate_working_directory(args.working_directory),
            "fail_level": normalize_fail_level(args.fail_level),
        }
    except ValueError as exc:
        error(str(exc))
        return 1

    write_outputs(outputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

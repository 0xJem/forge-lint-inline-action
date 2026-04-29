#!/usr/bin/env python3
"""Validate release version state for CI and release workflows."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
RELEASE_RELEVANT_PATHS = {
    "VERSION",
    "action.yml",
    "mise.toml",
    "README.md",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    ".github/workflows/release-preview.yml",
}
RELEASE_RELEVANT_PREFIXES = ("scripts/", "tests/")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def error(message: str) -> None:
    print(f"::error::{message}", file=sys.stderr)


def read_version() -> str:
    version_path = ROOT / "VERSION"
    if not version_path.exists():
        raise ValueError("VERSION file is missing")
    return version_path.read_text(encoding="utf-8").strip()


def validate_version(version: str) -> None:
    if version.startswith("v"):
        raise ValueError("VERSION must not start with 'v'")
    if not VERSION_RE.fullmatch(version):
        raise ValueError("VERSION must use MAJOR.MINOR.PATCH format")


def remote_tag_exists(version: str) -> bool:
    result = git(
        "ls-remote",
        "--exit-code",
        "--tags",
        "origin",
        f"refs/tags/v{version}",
        check=False,
    )
    return result.returncode == 0


def current_head() -> str:
    return git("rev-parse", "HEAD").stdout.strip()


def local_tag_commit(version: str) -> str | None:
    tag = f"refs/tags/v{version}"
    result = git("rev-parse", "-q", "--verify", tag, check=False)
    if result.returncode != 0:
        return None
    return git("rev-list", "-n", "1", f"v{version}").stdout.strip()


def changed_files(base_ref: str) -> set[str]:
    result = git("diff", "--name-only", f"{base_ref}...HEAD")
    return set(filter(None, result.stdout.splitlines()))


def is_release_relevant(path: str) -> bool:
    return path in RELEASE_RELEVANT_PATHS or path.startswith(RELEASE_RELEVANT_PREFIXES)


def validate_pr_mode(version: str, base_ref: str) -> None:
    if remote_tag_exists(version):
        raise ValueError(f"Version v{version} already exists")

    changed = changed_files(base_ref)
    relevant_changed = {path for path in changed if is_release_relevant(path)}
    if relevant_changed and "VERSION" not in changed:
        paths = ", ".join(sorted(relevant_changed))
        raise ValueError(
            f"Release-relevant files changed without updating VERSION: {paths}"
        )


def validate_release_mode(version: str, allow_current_tag: bool) -> None:
    tag_commit = local_tag_commit(version)
    if tag_commit is None:
        return

    if allow_current_tag and tag_commit == current_head():
        return

    raise ValueError(f"Version v{version} already exists")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pr", "release"), required=True)
    parser.add_argument("--base-ref", default="origin/master")
    parser.add_argument("--allow-current-tag", action="store_true")
    args = parser.parse_args()

    try:
        version = read_version()
        validate_version(version)
        if args.mode == "pr":
            validate_pr_mode(version, args.base_ref)
        else:
            validate_release_mode(version, args.allow_current_tag)
    except (ValueError, subprocess.CalledProcessError) as exc:
        message = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            message = exc.stderr.strip() or exc.stdout.strip() or message
        error(message)
        return 1

    print(f"Release validation passed for v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

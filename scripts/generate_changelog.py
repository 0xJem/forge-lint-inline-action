#!/usr/bin/env python3
"""Generate a release changelog from Conventional Commit subjects."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys


COMMIT_RE = re.compile(
    r"^(?P<type>build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(?:\((?P<scope>[a-z0-9][a-z0-9._-]*)\))?"
    r"(?P<breaking>!)?: (?P<summary>.+)$"
)
CATEGORIES = (
    ("Breaking Changes", lambda item: item["breaking"]),
    ("Features", lambda item: item["type"] == "feat" and not item["breaking"]),
    ("Fixes", lambda item: item["type"] == "fix" and not item["breaking"]),
    ("Performance", lambda item: item["type"] == "perf" and not item["breaking"]),
    ("Documentation", lambda item: item["type"] == "docs" and not item["breaking"]),
    (
        "CI and Maintenance",
        lambda item: (
            item["type"] in {"build", "chore", "ci", "refactor", "style", "test"}
            and not item["breaking"]
        ),
    ),
    ("Reverts", lambda item: item["type"] == "revert" and not item["breaking"]),
)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def parse_subject(subject: str, short_sha: str) -> dict[str, str | bool] | None:
    match = COMMIT_RE.fullmatch(subject)
    if not match:
        return None

    return {
        "type": match.group("type"),
        "scope": match.group("scope") or "",
        "breaking": bool(match.group("breaking")),
        "summary": match.group("summary"),
        "sha": short_sha,
    }


def release_range(base_ref: str | None, head_ref: str) -> str:
    if base_ref:
        return f"{base_ref}..{head_ref}"
    return head_ref


def commit_items(base_ref: str | None, head_ref: str) -> list[dict[str, str | bool]]:
    output = git(
        "log",
        "--reverse",
        "--format=%h%x00%s",
        release_range(base_ref, head_ref),
    )
    items = []
    for line in output.splitlines():
        short_sha, subject = line.split("\0", 1)
        item = parse_subject(subject, short_sha)
        if item:
            items.append(item)
    return items


def full_changelog_url(
    repo: str | None, base_ref: str | None, head_ref: str
) -> str | None:
    if not repo:
        return None
    if base_ref:
        base = base_ref.removeprefix("refs/remotes/origin/").removeprefix("origin/")
        return f"https://github.com/{repo}/compare/{base}...{head_ref}"
    return f"https://github.com/{repo}/commits/{head_ref}"


def render(
    items: list[dict[str, str | bool]],
    repo: str | None,
    base_ref: str | None,
    head_ref: str,
) -> str:
    lines = []
    included = set()

    for title, predicate in CATEGORIES:
        category_items = [item for item in items if predicate(item)]
        if not category_items:
            continue
        lines.append(f"## {title}")
        lines.append("")
        for item in category_items:
            included.add(str(item["sha"]))
            scope = f"**{item['scope']}:** " if item["scope"] else ""
            lines.append(f"- {scope}{item['summary']} ({item['sha']})")
        lines.append("")

    other_items = [item for item in items if str(item["sha"]) not in included]
    if other_items:
        lines.append("## Other Changes")
        lines.append("")
        for item in other_items:
            scope = f"**{item['scope']}:** " if item["scope"] else ""
            lines.append(f"- {scope}{item['summary']} ({item['sha']})")
        lines.append("")

    if not lines:
        lines.extend(
            ["No release notes generated from Conventional Commit subjects.", ""]
        )

    url = full_changelog_url(repo, base_ref, head_ref)
    if url:
        lines.extend([f"**Full Changelog**: {url}", ""])

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--repo")
    args = parser.parse_args()

    try:
        items = commit_items(args.base_ref, args.head_ref)
        print(render(items, args.repo, args.base_ref, args.head_ref), end="")
    except (ValueError, subprocess.CalledProcessError) as exc:
        message = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            message = exc.stderr.strip() or exc.stdout.strip() or message
        print(f"::error::{message}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

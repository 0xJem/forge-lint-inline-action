#!/usr/bin/env python3
"""Generate a release changelog from pull request titles."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable


PR_NUMBER_RE = re.compile(
    r"(?:\(#(?P<squash>\d+)\)|pull request #(?P<merge>\d+))", re.IGNORECASE
)
TITLE_RE = re.compile(
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


def run(command: list[str]) -> str:
    return subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def git(*args: str) -> str:
    return run(["git", *args])


def release_range(base_ref: str | None, head_ref: str) -> str:
    if base_ref:
        return f"{base_ref}..{head_ref}"
    return head_ref


def unique_preserving_order(values: Iterable[int]) -> list[int]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def pr_numbers_from_git(base_ref: str | None, head_ref: str) -> list[int]:
    output = git(
        "log",
        "--reverse",
        "--format=%B%x00END_COMMIT%x00",
        release_range(base_ref, head_ref),
    )
    numbers = []
    for match in PR_NUMBER_RE.finditer(output):
        number = match.group("squash") or match.group("merge")
        numbers.append(int(number))
    return unique_preserving_order(numbers)


def current_pr_number(event_path: str | None) -> int | None:
    if not event_path:
        return None
    with open(event_path, encoding="utf-8") as handle:
        event = json.load(handle)
    number = event.get("pull_request", {}).get("number")
    return int(number) if number else None


def fetch_pr(repo: str, number: int) -> dict[str, object]:
    output = run(
        [
            "gh",
            "api",
            f"/repos/{repo}/pulls/{number}",
            "--jq",
            "{number: .number, title: .title, html_url: .html_url}",
        ]
    )
    return json.loads(output)


def parse_title(pr: dict[str, object]) -> dict[str, object]:
    title = str(pr["title"])
    match = TITLE_RE.fullmatch(title)
    if match:
        return {
            "type": match.group("type"),
            "scope": match.group("scope") or "",
            "breaking": bool(match.group("breaking")),
            "summary": match.group("summary"),
            "number": int(pr["number"]),
            "url": str(pr["html_url"]),
        }

    return {
        "type": "other",
        "scope": "",
        "breaking": False,
        "summary": title,
        "number": int(pr["number"]),
        "url": str(pr["html_url"]),
    }


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
    items: list[dict[str, object]],
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
            included.add(int(item["number"]))
            scope = f"**{item['scope']}:** " if item["scope"] else ""
            lines.append(
                f"- {scope}{item['summary']} ([#{item['number']}]({item['url']}))"
            )
        lines.append("")

    other_items = [item for item in items if int(item["number"]) not in included]
    if other_items:
        lines.append("## Other Changes")
        lines.append("")
        for item in other_items:
            lines.append(f"- {item['summary']} ([#{item['number']}]({item['url']}))")
        lines.append("")

    if not lines:
        lines.extend(["No merged pull requests found for this release range.", ""])

    url = full_changelog_url(repo, base_ref, head_ref)
    if url:
        lines.extend([f"**Full Changelog**: {url}", ""])

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--current-pr-number", type=int)
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH"))
    args = parser.parse_args()

    try:
        numbers = pr_numbers_from_git(args.base_ref, args.head_ref)
        current = args.current_pr_number or current_pr_number(args.event_path)
        if current:
            numbers = unique_preserving_order([*numbers, current])
        prs = [fetch_pr(args.repo, number) for number in numbers]
        items = [parse_title(pr) for pr in prs]
        print(render(items, args.repo, args.base_ref, args.head_ref), end="")
    except (ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        message = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            message = exc.stderr.strip() or exc.stdout.strip() or message
        print(f"::error::{message}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

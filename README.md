# Forge Lint Inline Action

Run `forge lint` in GitHub Actions and surface findings as inline workflow annotations.

This action is intentionally small: it uses a composite action and a Python stdlib parser. It does not require Node, npm, `jq`, or a bundled build artifact.

## Why Annotations

V1 emits GitHub Actions annotations only. That keeps permissions minimal and works on pull requests without `pull-requests: write`.

Inline workflow annotations are the `::error`, `::warning`, and `::notice` messages that GitHub Actions attaches to workflow logs and, when file and line metadata is available, to changed files in the pull request UI. They are not pull request review comments, they do not create conversation threads, and they do not require write access to pull requests.

GitHub Actions annotations cannot render review-comment suggestion blocks. If Forge exposes suggested replacements, this action includes them as plain text in the annotation body.

For a live example of how the annotations appear on changed Solidity files, see the [forge lint inline smoke test PR](https://github.com/0xJem/forge-lint-inline-smoke/pull/2/changes).

## Usage

```yaml
permissions:
  contents: read

steps:
  # actions/checkout v6.0.2
  - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd

  # 0xJem/forge-lint-inline-action v0.1.0 or a reviewed commit
  - uses: 0xJem/forge-lint-inline-action@<commit-sha>
```

Pin a Foundry version:

```yaml
- uses: 0xJem/forge-lint-inline-action@<commit-sha>
  with:
    foundry-version: v1.8.0
```

Pass additional `forge lint` arguments:

```yaml
- uses: 0xJem/forge-lint-inline-action@<commit-sha>
  with:
    args: "--severity high --severity gas"
    fail-level: warning
```

Skip Foundry installation if your runner already provides `forge`:

```yaml
- uses: 0xJem/forge-lint-inline-action@<commit-sha>
  with:
    install-foundry: false
```

## Inputs

| Input               | Default   | Description                                                                                              |
| ------------------- | --------- | -------------------------------------------------------------------------------------------------------- |
| `foundry-version`   | `stable`  | Foundry version passed to `foundry-rs/foundry-toolchain`. Examples: `stable`, `nightly`, `rc`, `v1.8.0`. |
| `install-foundry`   | `"true"`  | Whether to install Foundry before linting.                                                               |
| `foundry-cache`     | `"true"`  | Passed to the Foundry setup action's `cache` input.                                                      |
| `working-directory` | `"."`     | Directory where `forge lint` runs.                                                                       |
| `args`              | `""`      | Extra arguments appended to `forge lint`.                                                                |
| `fail-level`        | `warning` | One of `none`, `error`, `warning`, or `notice`.                                                          |

Boolean inputs can be written as YAML booleans or strings:

```yaml
with:
  install-foundry: false
  foundry-cache: "true"
```

GitHub action inputs are still delivered to composite actions as string values, so this action validates and normalizes them before running. Invalid boolean values, unknown `fail-level` values, an empty `foundry-version`, or a missing `working-directory` fail fast with a workflow error.

## Exit Behavior

The action runs:

```bash
forge lint --json --deny never
```

Then the parser decides whether the action fails:

| `fail-level` | Result                                                       |
| ------------ | ------------------------------------------------------------ |
| `none`       | Do not fail for parsed lint annotations.                     |
| `error`      | Fail if any error annotation is emitted.                     |
| `warning`    | Fail if any warning or error annotation is emitted.          |
| `notice`     | Fail if any notice, warning, or error annotation is emitted. |

If `forge lint` exits non-zero and the parser cannot find any usable diagnostics, the action fails and prints the raw Forge output.

## Permissions

```yaml
permissions:
  contents: read
```

No pull request write permission is required.

## Self-Hosted Runner Requirements

- `bash`
- `python3`
- Network access if `install-foundry` is `"true"`

## Development Checks

Development tools and task commands are pinned in `mise.toml`.
Formatting coverage is split by file family: Ruff formats Python, Taplo formats TOML, and dprint formats Markdown, YAML, and JSON. actionlint validates GitHub workflow syntax.

Install the pinned tools:

```bash
mise install
```

Run local fix-capable tasks:

```bash
mise run lint
mise run format
mise run build
mise run test
mise run validate
```

Run CI/check-only variants:

```bash
mise run lint-check
mise run format-check
mise run build-check
mise run test-check
mise run validate-check
```

Install the repository Git hooks:

```bash
mise run hooks-install
```

The `commit-msg` hook validates commit subjects before Git accepts them. Commit subjects must use Conventional Commit style:

```text
feat: add severity filtering
fix(parser): handle nested diagnostics
docs: clarify inline workflow annotations
ci!: change release approval flow
```

Allowed types are `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, and `test`.

The release workflow runs on demand with `workflow_dispatch`. It validates the release state, publishes the immutable version tag, updates the moving major tag, and creates the GitHub Release with generated release notes. The release notes are generated from pull request titles since the previous semver release tag and include links to the included PRs. The release workflow uses GitHub's automatic per-run `GITHUB_TOKEN`, scoped by the workflow `permissions` block to `contents: write`.

The release workflow defaults to a dry run. Dry runs validate the release state, compute the tags, build the generated changelog, and write a changelog preview to the workflow summary without pushing tags or creating a release. To preview a branch before merge, manually run the release workflow from that branch with `dry-run` enabled. To publish, run the workflow from `master` with `dry-run` disabled; the `release` environment can require maintainer approval before the job proceeds.

The published action also pins its Foundry setup dependency by commit SHA. The current SHA is the `v1.8.0` ref for `foundry-rs/foundry-toolchain`.

Workflow jobs keep `actions/checkout` as the first explicit step. Local composite actions, such as `./.github/actions/setup`, are loaded from the checked-out workspace and cannot be used before checkout has run.

## GitHub Actions Pinning

This repository pins third-party GitHub Actions by commit SHA and documents the human version next to the pin in YAML comments. That gives reproducible workflow behavior while keeping upgrades reviewable.

Best current practices for consumers:

- Pin this action to an immutable commit SHA for the strongest supply-chain control.
- Pin to a full release tag, such as `v0.1.0`, when you want a readable immutable release reference.
- Avoid moving tags like `v0` or `v1` in highly sensitive workflows unless you have a separate update review process.
- Review action permissions explicitly. This action only needs `contents: read`.

Example SHA pin:

```yaml
- uses: 0xJem/forge-lint-inline-action@<commit-sha>
```

## Version Pinning

Immutable version tags use the full version:

```yaml
uses: 0xJem/forge-lint-inline-action@v0.1.0
```

Moving major tags track compatible updates before the next major:

```yaml
uses: 0xJem/forge-lint-inline-action@v0
```

Before `v1.0.0`, breaking changes may happen between minor versions. After `v1.0.0`, patch versions are bug fixes, minor versions are backward-compatible feature releases, and major versions can include breaking changes.

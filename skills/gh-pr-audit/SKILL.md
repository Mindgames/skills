---
name: gh-pr-audit
description: "Perform a full local audit of one or more GitHub PRs, run repository-native deterministic checks, apply result labels, and post a structured review comment. Use when a PR in this repo or under projects/* needs a deep, evidence-based review across any language or stack."
---

# Github Pull Request Audit and Review

## Overview

Use this skill to review repository pull requests. If multiple PRs are requested, process them one by one and link all of them in your final output.

The skill fetches each PR locally, analyzes the full diff, runs deterministic checks that already exist in the repository, evaluates GitHub PR checks, and posts a single review verdict with one of three result labels.

## Core rule: do not assume tooling

- Never assume Python, pytest, Node, Go, Rust, Docker, or any specific stack.
- Always discover how the repo expects validation to run before executing checks.
- Treat repository guidance as source of truth, especially `AGENTS.md`.

## Python launcher portability guard

If you need to run this skill's helper script or any Python command, resolve and reuse
`PYTHON_BIN` first:

```bash
PYTHON_BIN="$(command -v python3 || command -v python || true)"
[ -n "$PYTHON_BIN" ] || { echo "No Python interpreter found" >&2; exit 1; }
```

Never run raw `python ...` in shell commands.

## Quick start

`"$PYTHON_BIN" "scripts/review_pr.py" --repo "." --pr "<number-or-url>" --post`

Use `--json` for machine-friendly output.
Use `--project-filter projects/<slug>` to scope to one subproject.
Use `--run-tests` only when the impacted project explicitly uses Python + pytest.

The script provides a baseline audit. For full review quality, always run the repository-native checks you discover from project instructions.

## Workflow

1. Confirm `gh` authentication (`gh auth status`).
2. Resolve the PR number from `--pr` or current branch PR.
3. Discover repository instructions before running tests/checks:
   - Read `AGENTS.md` at repo root and in impacted project paths.
   - Read local docs that define validation commands (`README*`, `PROJECT.md`, `Makefile`, `justfile`, CI workflows, task runner configs).
4. Fetch PR head, fetch base branch, create a detached local worktree at the PR head.
5. Gather changed files from `base..head`, map file paths to impacted projects.
6. Build a deterministic check plan from discovered commands, prioritizing:
   - commands explicitly required by `AGENTS.md` or project docs
   - commands used by CI for the same paths
   - language/framework-native commands already present in the repo
7. Run checks from that plan and collect concrete evidence (pass/fail, logs, skipped reasons).
8. Evaluate GitHub check status (`gh pr checks`) and combine with local evidence.
9. Audit the PR and determine whether the issue was actually resolved with sufficient confidence.
10. If `--post` is set, apply one label and write one PR comment:
   - `pr-review/approved`
   - `pr-review/needs-changes`
   - `pr-review/uncertain`
11. Return only after a final status and evidence block is produced.

## Check discovery guidance

- Prefer explicit repo commands over guessed commands.
- If instructions conflict, prefer the most specific scope (changed project > repo root defaults).
- If a required tool is unavailable locally, report it as a confidence gap and keep the verdict conservative.
- Use fallback generic checks only when the repo provides no usable guidance.

## Optional browser fallback with agent-browser-relay

Use local environment or project-defined containers to test implementation. If frontend/browser validation is needed, use `agent-browser-relay`.

Required relay step pattern:

- `npm run relay:start`
- `node scripts/read-active-tab.js --check --wait-for-attach ...`
- proceed only after human confirms Chrome tab attachment.

## Outputs

- `verdict`: one of `approved`, `needs-changes`, `uncertain`
- `confidence_percent`: numeric confidence score
- `findings`: file-level and project-level findings with evidence
- `post_actions`: comment and label actions when `--post` is used

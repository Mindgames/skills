---
name: github-process-agent-issues
description: "Sweep GitHub issues labeled Agent across local repositories and process each as a dedicated PR with deterministic status labels and comments."
---

# Github Process Agent Issues

Use this skill to automate the manual review-and-fix cadence for GitHub issues tagged `Agent` in all git repositories discovered under the current working tree.

## Scope and triggers
- Use for requests involving:
  - "work through Agent issues"
  - "sweep issues labeled Agent"
  - "claim next Agent issue"
  - "submit PR for solved issue"
  - local repositories under the current folder or `projects/<slug>/` subfolders

Shortcut: `$github-process-agent-issues`

## Required companion skills
- `$branch`
- `$agent-browser-relay`
- `$commit-push`
- `$pr`
- `$shell-glob-safe-paths` when paths include `[]`, `()`, `*`, `?`, or spaces.

## Preconditions
1. Confirm GitHub CLI authentication with `gh auth status`.
2. Confirm the active workspace contains cloned repos with remotes.
3. Confirm these companion skills are available: `$branch`, `$agent-browser-relay`, `$commit-push`, `$pr`.
4. Run with network access and write permission for these repos.
5. Resolve portable Python launcher once before using helper scripts:
   - `PYTHON_BIN="$(command -v python3 || command -v python || true)"; [ -n "$PYTHON_BIN" ] || { echo "No Python interpreter found" >&2; exit 1; }`
   - Never invoke raw `python ...`.

## Core workflow
1. Find open `Agent` issues across all repos.
2. Process issues one at a time.
3. For each issue:
   - Inspect and claim the issue using `gh` commands.
   - Create a dedicated branch for the issue using `$branch`.
   - Implement the fix on that branch.
   - Run all required checks/tests (at minimum local lint/tests/build where available).
   - If any UI/frontend verification is needed, verify via `$agent-browser-relay`.
   - Commit and push using `$commit-push`.
   - Create/update PR using `$pr`.
   - Update issue and PR labels/comments with `gh` and stop if confidence is low.
4. Repeat until queue is empty.

## Mandatory behavior
- All GitHub operations must use the GitHub CLI (`gh`) or this skill's helper scripts that call `gh` under the hood.
- Use `gh` to:
  - list and inspect issues
  - add/remove issue labels
  - post issue comments and status updates
  - check and manage PR state
- Always follow a branch-first approach: do not solve an issue without creating or checking out a dedicated branch first.
- Only progress to the next issue after all required checks pass and PR is created/updated for the current issue.
- Do not bypass human confirmation on sensitive changes.
- Quote any literal path containing shell-glob characters before running shell commands:
  - `sed -n '1,120p' 'app/dashboard/[[...path]]/page.tsx'`
  - `sed -n '1,120p' 'app/research/[slug]/page.tsx'`

## Script entry points
The skill ships with:

- `scripts/agent_issue_sweep.py`

Use `--help` on any command for full flags and defaults.

### 1) Discover Agent issues
```bash
"$PYTHON_BIN" "scripts/agent_issue_sweep.py" discover \
  --root "." \
  --label "Agent"
```

This command scans every repo under `--root` and outputs issue rows grouped by repository.

### 2) Claim one issue for work context
```bash
"$PYTHON_BIN" "scripts/agent_issue_sweep.py" claim \
  --root "." \
  --issue owner/repo#123 \
  --base-branch "main"
```

Use this only to discover the issue and set working context. The workflow for this skill must still explicitly create/confirm the dedicated issue branch with `$branch`.

### 3) (Legacy helper for finalize) Finish one issue
```bash
"$PYTHON_BIN" "scripts/agent_issue_sweep.py" finalize \
  --root "." \
  --issue owner/repo#123 \
  --result approved \
  --run-tests
```

This helper should be treated as a compatibility fallback. Primary required path is:
1) branch via `$branch`
2) verify and test
3) push via `$commit-push`
4) PR via `$pr`

### 4) Required label and comment flow (via gh)
- Add/remove labels with `gh issue edit` and `gh pr edit`.
- Post final status on issue and PR with `gh issue comment` and `gh pr comment`.
- Apply labels:
  - `agent/in-progress` while working
  - `agent/resolved` for approved outcomes
  - `agent/blocking` for blocked/uncertain outcomes

## Mandatory certainty gate
- Default behavior requires full confidence (100) before finalizing.
- If confidence is below 100, pause and do not finalize the PR/issue; request explicit confirmation before continuing.

## Human handoff and in-depth checks
- You are still responsible for implementation quality in the branch.
- For human-verification gates (for example CAPTCHA), stop immediately, alert the user, and wait for explicit human confirmation before continuing.

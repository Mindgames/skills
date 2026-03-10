---
name: github-sync
description: Sync a local Git repository with its remote safely. Use when an agent needs to update a repo before starting work, fast-forward a local branch from `origin`, confirm that local `main` or another branch matches the remote, or prepare an up-to-date base branch before creating a new branch.
---

# GitHub Sync

## Overview

Use `scripts/sync-repo.sh` instead of rewriting ad-hoc `git fetch` and `git pull` logic. The script resolves the sync target, creates a local tracking branch when needed, and only performs fast-forward updates.

## Workflow

1. Check whether the user wants the remote default branch, a specific branch, or the current branch.
2. Prefer `origin` unless the user explicitly asks for another remote.
3. Run the bundled script:

```bash
scripts/sync-repo.sh
scripts/sync-repo.sh --branch main
scripts/sync-repo.sh --current
```

4. If the script reports that a branch switch would be unsafe because the worktree is dirty, stop and ask the user instead of stashing, resetting, or forcing the switch.
5. After a successful sync, use `git status -sb` when the user wants explicit verification.

## Branch Selection

- No flags: sync the remote default branch from `origin/HEAD`.
- `--branch <name>`: sync that branch from `origin/<name>`.
- `--current`: sync the currently checked out branch without switching away first.

## Hard Rules

- Never auto-stash, reset, rebase, or create a merge commit as part of sync.
- Use fast-forward-only updates.
- Never delete local branches or remote branches as part of sync.
- If `origin/HEAD` is unavailable and no explicit branch was provided, stop and ask which branch to sync.
- If the requested remote branch does not exist, stop and report the missing branch clearly.
- For branch-creation workflows that must branch from updated `main`, run `scripts/sync-repo.sh --branch main` first.

## Script

- `scripts/sync-repo.sh`: fetches from `origin`, resolves the target branch, creates a local tracking branch when needed, and fast-forwards it safely.

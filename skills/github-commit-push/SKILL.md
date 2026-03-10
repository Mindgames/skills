---
name: github-commit-push
description: Run lint/build checks before committing and pushing code, then optionally create a PR via GitHub CLI. Use when a user asks to commit/push changes or requests a pre-push verification workflow.
---

# Commit Push

## Overview

Provide a repeatable commit-and-push workflow that runs lint/build checks first and optionally creates a PR with GitHub CLI.

## Path Resolution (avoid missing-skill errors)

- Always open this skill using the absolute path from the active session skills list (for example `<agent-skills-root>/github-commit-push/SKILL.md`).
- Do not try guessed repo-relative skill paths unless the session explicitly lists that exact path.

## Workflow

1. Preflight
   - Run `git status -sb` and `git branch --show-current`; confirm branch and scope.
   - Determine the issue number to auto-close in PR:
     - Detect issue number from branch name patterns such as `issue-123`, `fix/123-*`, `gh-123`, `#123`, `23-*`.
     - If no issue can be derived automatically, ask the user for the issue number before creating the PR.
     - Keep the issue number only if a single, confirmed target exists.
   - If the user wants only specific files, confirm the file list before staging; otherwise default to all changes.
2. Verify
   - Run `pnpm lint`.
   - Run `pnpm knip`.
   - Run `pnpm build`. If repo policy restricts builds, ask the user to run it or explicitly approve running it.
   - If any command fails, stop and report the error.
3. Commit
   - Stage all changes: `git add -A`.
   - Summarize staged diff: `git diff --stat --cached`.
   - If no commit message is provided, generate a concise one based on the staged diff and proceed without asking.
   - Commit with `git commit -m "message"`.
4. Push
   - Push the current branch with `git push` (default behavior when nothing else is specified).
   - If no upstream is set, use `git push -u origin <branch>`.
5. PR (optional)
   - Ask whether to create a PR.
   - If yes and `gh` is available/authenticated:
     - Include issue closure metadata in the PR body using `Fixes #<issue-number>` (or `Closes #<issue-number>`) so merge will auto-close the issue.
     - Build a detailed PR body that follows the repository template (create `.github/pull_request_template.md` if missing).
     - Fill the template sections (Summary, Why, What changed, How, Testing, Notes, Checklist).
     - Add an explicit heading in the PR body such as:
       - `## Related issue`
       - `Fixes #<issue-number>`
     - Include test results and any warnings in Testing/Notes.
     - Run `gh pr create --title "<branch>: <summary>" --body "<filled template>"` (add `--draft` if requested) and share the PR link.
    - If `gh` is unavailable, explain how to proceed or skip PR creation.

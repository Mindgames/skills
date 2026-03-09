---
name: branch
description: Use when a user asks to create a new local git branch and start issue work (for example, "create branch" or "start working on issue XYZ"). Use this for issue-based branch naming in the `type/scope-short-description` pattern and for always syncing local `main` from `origin/main` before creating the new branch, creating the local tracking `main` branch first when needed.
---

# Branch Create

## Path Resolution (avoid missing-skill errors)

- Always open this skill using the absolute path from the active session skills list (for example `~/.codex/skills/branch/SKILL.md`).
- Do not use repo-relative `.codex/skills/...` or `.agents/skills/...` paths unless the session explicitly lists that exact path.
- If you see an error like `.../.codex/skills/public/branch/SKILL.md: No such file or directory`, immediately switch to `~/.codex/skills/branch/SKILL.md` and continue.

## Workflow

1. Confirm the issue target (for example `#123`, `123`, or an issue URL). If missing, ask the user for it.
2. Identify the branch type.
   - Prefer issue labels if available.
   - Suggested defaults: `feature`, `bugfix`, `chore`, `docs`, `refactor`, `test`, `release`.
   - If ambiguous, ask the user to choose.
3. Identify scope.
   - Use issue metadata if available (component, area, or team).
   - If unavailable, ask for a short scope token.
4. Build the short description from the issue title.
   - Lowercase.
   - Remove stop words and punctuation.
   - Replace whitespace with hyphens.
   - Keep concise (recommended <= 5 words).
   - Limit final slug length to keep the branch name manageable.
5. Form branch name as `type/scope-short-description`.
   - Examples:
      - `bugfix/api-auth-token-refresh`
      - `feature/dashboard-lien-card`
      - `chore/ci-fix-cache-busting`
6. Verify the repository can branch from `main`.
   - Confirm the repo has an `origin` remote.
   - Confirm `origin/main` exists.
   - If switching to `main` would require leaving a dirty worktree, stop and ask the user instead of stashing or resetting anything.
7. Sync local `main` from `origin/main` before branching:
   - `git fetch origin main`
   - If local `main` exists: `git switch main`
   - If local `main` does not exist: `git switch -c main --track origin/main`
   - `git pull --ff-only origin main`
8. Create branch locally from updated `main`:
   - `git switch -c "<branch-name>"`
9. Set issue start-work state in GitHub before coding (execution mode).
   - Add in-progress label:
     - `gh issue edit <issue> --add-label "agent/in-progress"`
   - Remove conflicting status labels when present:
     - `gh issue edit <issue> --remove-label "agent/resolved" || true`
     - `gh issue edit <issue> --remove-label "agent/blocking" || true`
     - `gh issue edit <issue> --remove-label "Blocked" || true`
   - Post a start comment that includes branch name:
     - `gh issue comment <issue> --body "Status: in progress. Branch: <branch-name>. Owner mode: Agent/Hybrid/Human."`
   - If your repo uses a project board status field, also move the item to `In progress`.
10. Report the branch name and current status with:
   - `git status -sb`

## Hard rules

- Create a local branch only (do not push unless explicitly requested).
- Always branch from an updated local `main` that matches `origin/main`.
- For issue-driven execution, do not start implementation until the issue is marked `agent/in-progress` (or user explicitly says not to mutate GitHub).
- Never stash, reset, or rebase just to make the branch creation succeed.
- Do not run branch resets/rebases/cherrypicks unless explicitly instructed.
- If the repository has no `main` branch, stop and ask the user for the correct base branch.
- If `origin/main` is missing, stop and ask the user for the correct remote base branch.

## Optional issue metadata enrichment (when `gh` is available)

- Try `gh issue view <issue> --json number,title,labels` when possible.
- Use labels to infer type.
- Use the title to derive a short description.
- If metadata is unavailable, continue with user-provided values.

## Optional issue creation (when user asks to create one first)

- If the user asks you to open an issue before branching, avoid inline `--body "..."` for multiline Markdown.
- Use a temp file with `gh issue create --body-file` to prevent shell quoting/backtick interpolation bugs:
  - `BODY_FILE=$(mktemp)`
  - `cat > "$BODY_FILE" <<'EOF'` ... `EOF`
  - `gh issue create --title "<title>" --body-file "$BODY_FILE"`
  - `rm -f "$BODY_FILE"`

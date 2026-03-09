---
name: github-pull-request
description: "Use when the user asks to create a pull request. Build a complete PR using best-practice structure with rich details on changes, verification, QA evidence, risks, and rollout notes. Include issue linkage and clear testing commands/results in the PR body."
---

# Github Pull Request

## Path Resolution (avoid missing-skill errors)

- Always open this skill using the absolute path from the active session skills list (for example `~/.codex/skills/github-pull-request/SKILL.md`).
- Do not try repo-relative `.codex/skills/...` or `.agents/skills/...` paths unless the session explicitly lists that exact path.
- If you hit a missing-skill error from an old path, re-open this skill from the active session skills list and continue (do not retry repo paths).

## Workflow

1. Confirm branch and scope
   - Run `git branch --show-current`.
   - If branch looks wrong for the requested work, ask for correction.
2. Gather change context
   - Run `git status -sb`.
   - Run `git diff --stat origin/$(git rev-parse --abbrev-ref @{upstream}..HEAD)` when upstream exists.
   - If no upstream exists, use `git diff --stat` and `git diff` against the likely target branch.
3. Decide PR title
   - Follow `type(scope): short imperative summary` format.
   - Keep title under 72 chars where possible.
4. Build PR body from required sections:
   - Summary
   - Why this change
   - What changed (bullets grouped by feature/file area)
   - Files changed
   - QA / testing (exact commands + outcomes)
   - Risk and impact
   - Rollback plan
   - Related issues
   - Checklist
5. Identify related issue(s)
   - Parse issue number from branch if present (examples: `123`, `issue-123`, `fix/123-...`).
   - Add `Fixes #<issue>` or `Closes #<issue>` in the PR body when confirmed.
6. Push branch if needed
   - If branch has no upstream, run `git push -u origin <branch>`.
7. Pre-create guards (avoid `gh pr create` hard failures)
   - Check whether an open PR already exists for this branch:
     - `gh pr list --head <branch> --state open --json number,url`
     - If one exists, stop and report the existing PR link instead of creating a duplicate.
   - Check commit delta against intended base branch before create:
     - `git rev-list --count <base>..HEAD`
     - If count is `0`, stop and report "no commits to open PR against `<base>`" with next action:
       - verify current repo/branch, or
       - push the intended commits, or
       - switch to the correct branch.
8. Create PR
   - If user requested draft, pass `--draft`.
   - Write the PR body to a temp file and use `--body-file` to avoid shell quoting/interpolation bugs with Markdown/backticks.
   - Preferred pattern:
     - `BODY_FILE=$(mktemp)`
     - `cat > "$BODY_FILE" <<'EOF'` ... `EOF`
     - `gh pr create --title "<title>" --body-file "$BODY_FILE"`
     - `rm -f "$BODY_FILE"`
   - If `gh` auth is unavailable or user is not in GitHub environment, output the prepared title and body text for manual submission.
9. Report back
   - Include PR link if created, target branch, and review expectations.
   - Ask explicitly what should be prioritized in review.

## PR body template

```
## Summary
- ...

## Why
- ...

## What changed
- ...

## Files changed
- ...

## QA / Testing
- Command: `...` — Result: ...
- Command: `...` — Result: ...

## Risks and impacts
- ...

## Rollback plan
- ...

## Related issues
- Fixes #123 (optional)

## Checklist
- [ ] Tests pass
- [ ] No obvious regressions
- [ ] Documentation updated where needed
- [ ] Rollback path documented
```

## Hard rules

- Never submit a PR without a QA/testing section.
- Never claim tests passed without listing exact commands and outputs.
- Do not include secrets, credentials, or internal URLs in the PR description.
- Ask before adding reviewers/labels if not already provided.
- Never merge a PR automatically; only merge when the user explicitly instructs it.

## Optional metadata enrichment with gh

- Use `gh pr create` and `gh pr view` for consistency checks.
- If labels are requested, add after creation:
  - `gh pr edit <number> --add-label <label>`
- If reviewers are requested:
  - `gh pr edit <number> --add-reviewer <users>`

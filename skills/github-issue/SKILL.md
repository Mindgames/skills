---
name: github-issue
description: Create complete, implementation-ready GitHub issues from user input and publish them with `gh issue create`. Use when asked to create/file/open a new issue in any repository, including cases where requirements must be structured into clear scope, acceptance criteria, constraints, and done-when outcomes.
---

# GitHub Issue

## Overview
Turn rough requests into high-quality GitHub issues with clear delivery criteria, then create the issue via GitHub CLI.

## Workflow
1. Confirm GitHub CLI access.
2. Determine target repository.
3. Convert input into a structured issue body.
4. Create the issue with `gh issue create`.
5. Return the issue URL plus a concise summary of assumptions.

## Preconditions
- Run `gh auth status` before issue creation.
- Use explicit repo when provided (`--repo owner/repo`).
- Otherwise use current repository context.
- Do not use web UI for creation unless user explicitly requests it.

## Issue Quality Standard
Always include these sections in issue body markdown:
- `## Goal`
- `## Background`
- `## Scope`
- `## Requirements`
- `## Acceptance Criteria`
- `## Constraints`
- `## Out of Scope`
- `## Done When`

Write requirements as concrete bullets. Write acceptance criteria as testable outcomes.

## Missing Information Policy
- Infer sensible defaults for non-critical gaps and list them under `Assumptions`.
- Ask one blocking question only when repo target or core objective is unknown.
- Challenge vague requests by tightening scope and criteria instead of copying ambiguity.

## Execution Pattern
Use a temporary markdown file to avoid shell quoting issues.

```bash
cat > /tmp/github-issue.md <<'EOF'
## Goal
...
EOF

gh issue create \
  --title "<clear action-oriented title>" \
  --body-file /tmp/github-issue.md
```

Use explicit repository when needed:

```bash
gh issue create \
  --repo owner/repo \
  --title "<clear action-oriented title>" \
  --body-file /tmp/github-issue.md
```

## Response Contract
After creation, always provide:
- Issue URL
- Repo used
- Final title
- Assumptions made

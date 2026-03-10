---
name: project-github-issues
description: Create and manage GitHub issues for a multi-repo project, including milestones, project board linking, and sub-issues.
---

# Project GitHub Issues

## Overview
Use this skill to create well-structured issues across a target set of repositories, add milestones, link to a project board, and create true sub-issues (not just checklist items).

## Path Resolution (avoid missing-skill errors)

- Always open this skill using the absolute path from the active session skills list (for example `<agent-skills-root>/project-github-issues/SKILL.md`).
- Do not try guessed repo-relative skill paths unless the session explicitly lists that exact path.

## Repos and defaults
- Repos: `<owner>/<repo-a>`, `<owner>/<repo-b>`, `<owner>/<repo-c>`
- Project board: `<board title>` (owner: `<owner>`, project number: `<number>`)
- Milestones: use the milestone name provided by the user (e.g., "0.8")

## Workflow
1. Clarify repo and milestone if missing.
2. Draft concise issue body with: Goal, Scope, Acceptance criteria, Open questions.
3. Create issue with `gh issue create` and add milestone.
4. Add issue to the configured project board.
5. If items should be grouped, use sub-issues (GraphQL), not separate issues.

## Sub-issues (GitHub issue hierarchy)
Use GraphQL to create true sub-issues.

1) Get issue IDs:
```
gh api graphql -f query='query($owner:String!,$name:String!,$parent:Int!,$child:Int!){repository(owner:$owner,name:$name){parent:issue(number:$parent){id} child:issue(number:$child){id}}}' \
  -F owner=<owner> -F name=<repo> -F parent=429 -F child=430
```

2) Add sub-issue:
```
gh api graphql -f query='mutation($issueId:ID!,$subIssueId:ID!){addSubIssue(input:{issueId:$issueId,subIssueId:$subIssueId}){issue{number} subIssue{number}}}' \
  -F issueId=<PARENT_ID> -F subIssueId=<CHILD_ID>
```

3) Remove sub-issue if needed:
```
gh api graphql -f query='mutation($issueId:ID!,$subIssueId:ID!){removeSubIssue(input:{issueId:$issueId,subIssueId:$subIssueId}){issue{number} subIssue{number}}}' \
  -F issueId=<PARENT_ID> -F subIssueId=<CHILD_ID>
```

## Creating skills (when the issue is about agent skills)
- Use the `skill-creator` workflow.
- Default location: the user-scope agent skills directory selected by the active platform/installer, unless the user requests a project-local or public location.
- Initialize with `init_skill.py`, edit `SKILL.md`, then package with `package_skill.py`.
- Keep SKILL.md concise; put long docs in references when needed.

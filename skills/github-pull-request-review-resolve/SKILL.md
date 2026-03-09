---
name: github-pull-request-review-resolve
description: "Deeply audit a GitHub pull request, analyze review comments and threads, apply legitimate fixes, resolve addressed review threads, and repair failing CI/build checks. Use when asked to handle PR review feedback, close out reviewer comments, or fix failing PR checks before merge."
---

# GitHub Pull Request Review & Resolve

## Workflow

1. Confirm PR context and access.
- Run `gh auth status`.
- Identify PR number from user input or current branch with `gh pr view --json number,url,headRefName,baseRefName,reviewDecision`.
- Stop and report clearly if no PR is associated with the branch.

2. Collect full review and check signal before changing code.
- Read PR metadata:
  - `gh pr view <pr> --json number,title,url,headRefName,baseRefName,reviewDecision,mergeStateStatus,statusCheckRollup,files`
- Read top-level discussion:
  - `gh pr view <pr> --comments`
- Read inline review comments (including resolved/outdated context):
  - `gh api repos/{owner}/{repo}/pulls/<pr>/comments --paginate`
- Read review threads and unresolved state via GraphQL:
  - First resolve owner/repo:
    - `OWNER_REPO=$(gh repo view --json owner,name -q '.owner.login + "/" + .name')`
    - `OWNER=${OWNER_REPO%/*}`
    - `REPO=${OWNER_REPO#*/}`
  - Then query:

```bash
gh api graphql -F owner="$OWNER" -F repo="$REPO" -F number=<pr> -f query='query($owner:String!,$repo:String!,$number:Int!){
  repository(owner:$owner,name:$repo){
    pullRequest(number:$number){
      reviewThreads(first:100){
        nodes{
          id
          isResolved
          isOutdated
          comments(first:20){
            nodes{
              author{login}
              body
              path
              line
              url
            }
          }
        }
      }
    }
  }
}'
```

3. Audit each reviewer point deeply before deciding action.
- Classify each point as one of:
  - `legitimate`: reproducible defect, correctness risk, security risk, regression risk, or clear maintainability issue.
  - `partially legitimate`: valid concern but proposed fix needs a different implementation.
  - `not legitimate`: preference-only or based on stale/misread context.
- Verify against current diff and base branch; do not assume a comment is still valid if code changed.
- Reproduce behavior with targeted local commands where possible.

4. Apply fixes for legitimate points.
- Make minimal, robust code changes that solve root cause.
- Add/update tests when behavior changes.
- Keep changes scoped to reviewed feedback and failing checks.
- Run relevant local validation commands and record exact commands and results.
- Commit and push updates to the PR branch.

5. Fix failing build/check errors on the PR.
- List check outcomes:
  - `gh pr checks <pr> --json name,bucket,state,workflow,link`
- For failed checks, inspect logs:
  - `gh run list --branch "$(gh pr view <pr> --json headRefName -q .headRefName)" --limit 20`
  - `gh run view <run-id> --log-failed`
- Reproduce the failing step locally whenever possible, implement a fix, rerun local validation, and push.
- If a failure cannot be reproduced locally, document evidence from CI logs and propose the smallest safe remediation.

6. Resolve review threads only when they are actually addressed.
- Reply with what changed and why (include file/behavior evidence).
- Resolve thread only after fix is pushed and verified.
- Use GraphQL mutation when resolution is supported:

```bash
gh api graphql -F threadId='<thread-id>' -f query='mutation($threadId:ID!){
  resolveReviewThread(input:{threadId:$threadId}){
    thread{isResolved}
  }
}'
```

- If a comment is `not legitimate`, respond respectfully with evidence and do not silently resolve without maintainer alignment.

7. Report completion clearly.
- Provide:
  - PR link
  - fixed review points
  - unresolved/contested points with rationale
  - checks fixed and current check status
  - residual risks or blockers
- Ask what to prioritize next in review.

## Hard Rules

- Never merge a PR automatically; merge only when the user explicitly instructs it.
- Never resolve a review thread without a pushed fix or explicit evidence-based rationale.
- Never claim checks are fixed without showing exact verification commands and outcomes.
- Never force-push, rebase, or rewrite PR history unless explicitly instructed.
- Never dismiss reviewer feedback without documenting the technical reasoning.
- Never leak secrets, tokens, or internal-only URLs in comments or PR updates.

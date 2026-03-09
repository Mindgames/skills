# GitHub Commands

Use these command patterns for repeatable milestone/cycle operations.

## Repo Health Snapshot (single repo)

```bash
gh api graphql -f query='
query($owner:String!, $name:String!) {
  repository(owner:$owner, name:$name) {
    issues(states:OPEN) { totalCount }
    pullRequests(states:OPEN) { totalCount }
    agent: issues(states:OPEN, filterBy:{labels:["Agent"]}) { totalCount }
    needsSpec: issues(states:OPEN, filterBy:{labels:["Needs-Spec"]}) { totalCount }
    defaultBranchRef { name }
    pushedAt
  }
}' -f owner="<owner>" -f name="<repo>"
```

## Oldest Open Issue / PR

```bash
gh api graphql -f query='
query($owner:String!, $name:String!) {
  repository(owner:$owner, name:$name) {
    oldestIssue: issues(states:OPEN, first:1, orderBy:{field:CREATED_AT, direction:ASC}) {
      nodes { number title createdAt url }
    }
    oldestPr: pullRequests(states:OPEN, first:1, orderBy:{field:CREATED_AT, direction:ASC}) {
      nodes { number title createdAt url }
    }
  }
}' -f owner="<owner>" -f name="<repo>"
```

## List Milestones

```bash
gh api "repos/<owner>/<repo>/milestones?state=all&per_page=100"
```

## Create Milestone

```bash
gh api "repos/<owner>/<repo>/milestones" \
  -f title="<milestone_name>" \
  -f due_on="<YYYY-MM-DD>T23:59:59Z" \
  -f description="<milestone_dod>"
```

## Update Milestone

```bash
gh api --method PATCH "repos/<owner>/<repo>/milestones/<number>" \
  -f title="<milestone_name>" \
  -f due_on="<YYYY-MM-DD>T23:59:59Z" \
  -f description="<milestone_dod>" \
  -f state="open"
```

## Create Issue

```bash
gh issue create \
  --repo "<owner>/<repo>" \
  --title "<title>" \
  --body-file "<path/to/body.md>" \
  --label "Agent" \
  --milestone "<milestone_name>"
```

## Edit Issue Labels / Milestone

```bash
gh issue edit <issue_number> \
  --repo "<owner>/<repo>" \
  --add-label "Agent" \
  --remove-label "Needs-Spec" \
  --milestone "<milestone_name>"
```

## Project V2 Item Query (GraphQL)

```bash
gh api graphql -f query='
query($org:String!, $num:Int!) {
  organization(login:$org) {
    projectV2(number:$num) {
      title
      items(first:100) {
        nodes {
          id
          content {
            ... on Issue { number title url state }
            ... on PullRequest { number title url state }
          }
        }
      }
    }
  }
}' -f org="<org>" -F num=<project_number>
```

## Practical Notes

1. Prefer GraphQL for counts and portfolio snapshots.
2. Use REST only when creating/editing milestones or issues.
3. Always print a before/after summary after batch operations.

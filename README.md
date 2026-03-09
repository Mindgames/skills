# GitHub Skills

Staged reusable Codex skills for GitHub workflows.

## Skills

| Skill | What it does |
| --- | --- |
| `gh-address-comments` | Help address review/issue comments on the open GitHub PR for the current branch using gh CLI; verify gh auth first and prompt the user to authenticate if not logged in. |
| `gh-fix-ci` | Use when a user asks to debug or fix failing GitHub PR checks that run in GitHub Actions; use `gh` to inspect checks and logs, summarize failure context, draft a fix plan, and implement only after explicit approval. Treat external providers (for example Buildkite) as out of scope and report only the details URL. |
| `gh-pr-audit` | Perform a full local audit of one or more GitHub PRs, run repository-native deterministic checks, apply result labels, and post a structured review comment. Use when a PR in this repo or under projects/* needs a deep, evidence-based review across any language or stack. |
| `github-commit-push` | Run lint/build checks before committing and pushing code, then optionally create a PR via GitHub CLI. Use when a user asks to commit/push changes or requests a pre-push verification workflow. |
| `github-issue` | Create complete, implementation-ready GitHub issues from user input and publish them with `gh issue create`. Use when asked to create/file/open a new issue in any repository, including cases where requirements must be structured into clear scope, acceptance criteria, constraints, and done-when outcomes. |
| `github-label-agent-issues` | Scan open GitHub issues and label those suitable for autonomous Agent execution with `Agent`; flag unclear candidates with `Needs-Spec`, enforce milestone alignment, and surface project/milestone-cycle planning gaps. |
| `github-milestone-cycle-ops` | Plan and run milestone/cycle operations for multi-repo projects in GitHub with a shared milestone per project. Use when defining or revising current/next milestones, deciding cycle load, shaping backlog into AI-ready issues, creating/updating milestones and issues across repos, reviewing GitHub project board health, or producing daily/weekly project execution plans. |
| `github-process-agent-issues` | Sweep GitHub issues labeled Agent across local repositories and process each as a dedicated PR with deterministic status labels and comments. |
| `github-pull-request-review-resolve` | Deeply audit a GitHub pull request, analyze review comments and threads, apply legitimate fixes, resolve addressed review threads, and repair failing CI/build checks. Use when asked to handle PR review feedback, close out reviewer comments, or fix failing PR checks before merge. |
| `github-sync` | Sync a local Git repository with its remote safely. Use when Codex needs to update a repo before starting work, fast-forward a local branch from `origin`, confirm that local `main` or another branch matches the remote, or prepare an up-to-date base branch before creating a new branch. |
| `project-github-issues` | Create and manage GitHub issues for a multi-repo project, including milestones, project board linking, and sub-issues. |

---
name: github-milestone-cycle-ops
description: Plan and run milestone/cycle operations for multi-repo projects in GitHub with a shared milestone per project. Use when defining or revising current/next milestones, deciding cycle load, shaping backlog into AI-ready issues, creating/updating milestones and issues across repos, reviewing GitHub project board health, or producing daily/weekly project execution plans.
---

# Github Milestone Cycle Ops

Run portfolio planning as a GitHub execution-control system, not a static roadmap. Keep all active projects loaded with AI-ready work while preserving value-first prioritization.

Use `gh` CLI + GraphQL for live state and act directly in GitHub (issues, milestones, project board updates). Treat documents as control surfaces for planning and execution routing.

## Operating Mode (Hard Gate)

This skill is `planning_only`.

Allowed actions:
1. Read context from control-plane files and GitHub.
2. Create/update milestones, issues, labels, and project board fields.
3. Write cycle-sync outputs to control-plane write-back paths.

Disallowed actions (unless user explicitly asks in a separate build task):
1. Editing source code in product repositories.
2. Creating implementation PRs or committing code changes.
3. Running build/test/lint as part of cycle planning.
4. Performing dependency upgrades in codebases.

If a request mixes planning and implementation, this skill must do planning + GitHub alignment only, then stop with an execution handoff list.

## Execution Context Model

Assume this skill may run inside an individual project repo, not inside control-plane root.

Resolve context in this order:

1. Local project repo files (current working repo)
2. control-plane central files at `$PORTFOLIO_ROOT` when present
3. Live GitHub state

Always use control-plane central goals/priorities to align local project planning.

## control-plane Context Sources

When control-plane is available, read these before finalizing a plan:

1. `$PORTFOLIO_ROOT/projects/README.md`
2. `$PORTFOLIO_ROOT/tasks.md`
3. `$PORTFOLIO_ROOT/projects/<slug>/PROJECT.md` for the current project
4. Latest GitHub ops report in `$PORTFOLIO_ROOT/operator/daily_notes/github-ops/`
5. Latest project-health snapshot in `$PORTFOLIO_ROOT/operator/daily_notes/`
6. Latest priority sync note in `$PORTFOLIO_ROOT/operator/daily_notes/priority-sync/`

If these sources conflict, prefer live GitHub execution truth, then update both local repo planning and control-plane planning notes.

## Operating Rules

1. Use one shared milestone name across all repos inside a project cycle.
2. Keep every active project supplied with actionable tasks so agents do not idle.
3. Prioritize value and speed-to-outcome over completeness or perfect planning.
4. Push back on overloading cycles; keep planned load at `70-85%` of realistic capacity.
5. Enforce AI-ready issue quality before loading work into an active cycle.
6. Use parent-first orchestration: if a control-plane parent project exists, run planning at parent level and include all child repos in one pass.
7. Run a priority-intake pass before any GitHub mutations (close/retarget/create/move).
8. Include full URL links for every referenced issue, PR, milestone, and board item.
9. End with one unambiguous next-step contract (single recommended action first).
10. If no fresh priority sync exists (older than 7 days), avoid destructive mutations and output `Priority Sync Needed`.

## Parent-First Scope Resolution

If control-plane exists, resolve scope like this:

1. Identify current repo.
2. Find matching parent project slug in `$PORTFOLIO_ROOT/projects/`.
3. If parent exists and lists multiple repos, run against the parent project, not a single child repo.
4. Apply one milestone plan across all repos in that parent project.
5. Only break parent-first mode if the child repo has an explicitly independent milestone charter documented in control-plane.

Example:

1. `project-alpha-web` or `project-alpha-api` context -> run on parent `project-alpha`.
2. `project-beta-web` or `project-beta-api` context -> run on parent `project-beta`.

## Workflow

### -2) Mode Lock (Mandatory)

1. Set run mode to `planning_only`.
2. Confirm no source-code edits will be performed.
3. Restrict all mutations to GitHub planning surfaces + control-plane write-back files.
4. If the task drifts toward coding, stop and return to milestone/issue/board operations.

### -1) Priority Sync (Mandatory)

1. Load latest priority sync artifact using [references/priority-sync-template.md](references/priority-sync-template.md):
   - human priorities per project
   - AI priorities per project
   - explicit decision outcomes when priorities conflict
2. Treat this artifact as hard guidance for cycle loading and issue ordering.
3. Parse `Execution Overrides` and apply them before general backlog heuristics.
4. If an override references a specific issue/PR URL, make it the first candidate in `Next Step (Do This Now)` unless blocked.
5. Freshness rule:
   - fresh: created within last 7 days
   - stale: older than 7 days
6. If stale or missing:
   - interactive run: request/update priority sync first
   - non-interactive run: continue in conservative mode, do not close issues/PRs, and emit `Priority Sync Needed`

### 0) Priority Intake (Mandatory)

1. Capture project priorities before execution:
   - top 1-3 outcomes for this cycle
   - constraints/non-goals
   - risk tolerance and speed preference
2. If interactive run, ask for missing priorities first.
3. If non-interactive automation, infer from:
   - latest priority sync note in `operator/daily_notes/priority-sync/`
   - `$PORTFOLIO_ROOT/tasks.md`
   - project `PROJECT.md`
   - latest GitHub ops + project-health notes
4. If priorities are still unclear, switch to plan-only mode and output `Priority Questions` instead of mutating GitHub.

### 1) Build Live Context

1. Resolve execution scope:
   - current repo scope
   - parent project scope in control-plane (preferred when available)
   - linked repos in same parent project
   - control-plane project slug mapping
2. Pull GitHub state for each repo:
   - open issues
   - open PRs
   - oldest stale issues
   - milestone progress
   - `Agent` and `Needs-Spec` label counts
3. Pull current GitHub project board columns/status totals and identify bottlenecks.
4. If business/technical uncertainty is high, run focused web/product research with $agent-browser before planning.

Use [references/github-commands.md](references/github-commands.md) for deterministic command patterns.

### 2) Define Current + Next Milestone

1. Keep exactly two planning horizons visible:
   - `Current milestone`: execution now
   - `Next milestone`: pre-shaped queue for immediate handoff
2. For multi-repo projects, apply the same milestone title + due date across all repos.
3. Write milestone DoD as outcome statements, not task lists.
4. Validate each milestone against:
   - measurable business or delivery value
   - feasibility in one cycle
   - dependency clarity

Use [references/milestone-patterns.md](references/milestone-patterns.md) for naming and DoD standards.

### 3) Shape Backlog Into AI-Ready Issues

Before loading work into a cycle, each issue must include:
1. Problem statement and target outcome
2. Acceptance criteria (testable)
3. Scope guardrails (what not to do)
4. Dependencies and blockers
5. Effort hint (`XS/S/M/L`) and impact (`H/M/L`)
6. Owner mode (`Agent`, `Human`, or `Hybrid`)

Use [references/issue-spec.md](references/issue-spec.md) for the exact template.

### 4) Compute Cycle Load

1. Estimate available capacity (human + agent) for the cycle.
2. Reserve `15-30%` slack for interrupts, reviews, and integration overhead.
3. Cap planned load to `70-85%` of realistic capacity.
4. Balance load using:
   - `60%` core value delivery (revenue/users/critical ship)
   - `30%` enabling work (automation, reliability, debt blocking velocity)
   - `10%` optional bets (R&D/opportunity pull)
5. Keep minimum flow for every active project:
   - at least 1 milestone-critical issue in progress
   - at least 2 AI-ready issues queued next

Use [references/cycle-load-model.md](references/cycle-load-model.md) for sizing heuristics.

### 5) Sync GitHub System-of-Execution

1. Create/update milestones across all repos in scope.
2. Create/update issues and attach the correct milestone.
3. Apply labels to enforce execution routing:
   - `Agent` for autonomous work
   - `Needs-Spec` for unclear scope
   - `Blocked` when waiting dependencies exist
4. Ensure project board status reflects true execution state.
5. Close or re-scope stale issues that no longer match current milestones.

### 6) Output the Plan and Action List

Always produce:
1. Milestone summary:
   - current milestone name, target, DoD
   - next milestone name, target, DoD
2. Cycle load table:
   - total capacity
   - planned load
   - slack
   - load split (`60/30/10`)
3. GitHub actions executed:
   - milestones created/updated
   - issues created/updated
   - board updates
4. Immediate next actions (top 5) with owner mode and due dates.
5. Priority alignment summary:
   - human priorities used
   - AI priorities used
   - resolved conflicts
   - priority sync file path + date

Formatting requirements:
1. Add full links for all items, for example:
   - `https://github.com/<owner>/<repo>/issues/<n>`
   - `https://github.com/<owner>/<repo>/pull/<n>`
   - `https://github.com/<owner>/<repo>/milestone/<n>`
2. Use absolute dates (`YYYY-MM-DD`) for due/target fields.
3. Avoid vague “next step” text; use the contract below.

Required final section:

`Next Step (Do This Now)` with:
1. `Action` (single action only)
2. `Why now` (one sentence, value + unblock)
3. `Target link` (one primary issue/PR URL)
4. `Execution checklist` (3-6 concrete steps)
5. `Done when` (testable acceptance)
6. `Owner mode` (`Agent|Human|Hybrid`)
7. `ETA` (for example `60-90 minutes`)
8. `Fallback` (what to do if blocked)

After producing output, write run results to control-plane using the contract in [references/control-plane-writeback.md](references/control-plane-writeback.md).

## Mandatory Write-Back

When control-plane exists, write:

1. Markdown report:
   - `$PORTFOLIO_ROOT/operator/daily_notes/project-cycle-sync/<YYYY-MM-DD>-<project-slug>-milestone-cycle-sync.md`
2. JSON report:
   - `$PORTFOLIO_ROOT/operator/daily_notes/project-cycle-sync/<YYYY-MM-DD>-<project-slug>-milestone-cycle-sync.json`

Include:

1. Current + next milestone and DoD
2. Cycle load and slack
3. GitHub changes made
4. Top risks and blockers
5. Next 5 actions

If control-plane path is unavailable, write the same files under:

- `<repo-root>/.codex/reports/milestone-cycle-sync/`

## Quality Gates

Do not mark a planning pass complete if any of these are true:
1. Active project has no clear current milestone DoD.
2. Active project has fewer than 3 AI-ready issues.
3. Milestone load exceeds `85%` of realistic capacity.
4. Multi-repo project has inconsistent milestone names/dates across repos.
5. Project board has stale status (issue state conflicts with board state).
6. Any product source file was edited during the run.

## Escalation and Pushback

Challenge non-optimal instructions when they reduce delivery speed or quality. Offer a better option with reasoned tradeoffs, then proceed with the best viable plan.

Examples:
1. If asked to load too much work in one cycle, reduce load and preserve slack.
2. If asked to keep vague issues in active milestones, move them to `Needs-Spec`.
3. If asked to focus only one project while others have no queued tasks, create thin-slice queues for each active project to avoid agent idle time.

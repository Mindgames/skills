---
name: github-label-agent-issues
description: "Scan open GitHub issues and label those suitable for autonomous Agent execution with `Agent`; flag unclear candidates with `Needs-Spec`, enforce milestone alignment, and surface project/milestone-cycle planning gaps."
---

# Github Issues Audit & Labeling

# Use this skill to scan open GitHub issues and apply the `Agent` label only when an issue is clearly suitable for AI-driven execution.

This skill is intentionally conservative: it can classify issues for automation, add clarifying comments when additional details are missing, and validate planning hygiene (milestones and project cycles).

## Scope and triggers
- Use when you need issue triage and pre-labeling, not implementation.
- Use for:
  - "label issues for Agent"
  - "mark auto-solvable issues with Agent"
  - "find candidate issues for github-process-agent-issues"

Shortcut: `$github-label-agent-issues`

## Preconditions
1. Confirm GitHub CLI authentication with `gh auth status`.
2. Confirm write access for target repositories.
3. Confirm all GitHub operations use `gh`.
4. If you want mutations, pass `--apply`; without it, only reports are generated.
5. Resolve portable Python launcher once and reuse it:
   - `PYTHON_BIN="$(command -v python3 || command -v python || true)"; [ -n "$PYTHON_BIN" ] || { echo "No Python interpreter found" >&2; exit 1; }`
   - Never invoke raw `python ...`.

## Core behavior
1. Discover local repositories under a workspace root (or a single explicit `--repo`).
2. Fetch open issues.
3. Exclude issues already labeled `Agent` or blocked by explicit disqualifier labels.
4. Score each issue with strict heuristics for:
   - clarity of scope
   - explicit acceptance criteria or reproducibility hints
   - implementation risk
   - external dependency / policy/architecture-heavy context
5. Apply labels:
   - `Agent` for high-confidence, safely automatable issues
   - `Needs-Spec` for well-meaning but underspecified issues
   - no label change for low-confidence or risky issues
6. Provide a concise per-repo report and skip any issue that is ambiguous.
7. For clarification-heavy issues, post comments with `@`-mentions requesting missing information.
8. Ensure milestone and planning health:
   - assign/ recommend milestones for qualifying Agent issues when possible
   - inspect project/board state and detect empty or closed project context
   - raise alerts if upcoming milestone cycles need planning
9. Use investigation mode where automation confidence is reduced:
   - avoid hard coding a final status
   - surface next checks (close/duplicate/fix verification) for human decision

## How to use

### Safe dry-run (recommended first pass)
```bash
"$PYTHON_BIN" "scripts/label_agent_issues.py" \
  --root "." \
  --threshold 78 \
  --max-issues 200 \
  --apply-needs-spec \
  --json
```

### Apply labels
```bash
"$PYTHON_BIN" "scripts/label_agent_issues.py" \
  --root "." \
  --apply \
  --threshold 78 \
  --max-issues 200 \
  --apply-needs-spec \
  --apply-comments \
  --auto-assign-milestone \
  --project-alert-days 14
```

### Target a single repo
```bash
"$PYTHON_BIN" "scripts/label_agent_issues.py" \
  --repo "owner/repo" \
  --apply \
  --apply-needs-spec \
  --apply-comments \
  --auto-assign-milestone \
  --project-alert-days 14
```

### Optional dry-run-only output format (no writes)
- `--json` prints a machine-readable array.
- default output prints a readable report grouped by repository.

### Clarification and mention policy
- If uncertainty markers are detected (`?`, "needs more info", "missing information", "clarif"), classify as needing clarification.
- Post comments when clarification is needed and tag people with `@` (minimum: issue author).
- Ask for concrete acceptance criteria, reproducible steps, and expected/actual behavior in comments.

## Heuristic labels and policy

### Positive fit signals
- Issue has clear, implementable action words in title/body (e.g., `fix`, `add`, `update`, `remove`, `implement`, `document`, `refactor`, `test`).
- Title + body provide either:
  - acceptance criteria, or
  - reproduce steps, or
  - expected/actual behavior.
- Issue scope is small/medium and has no known blocking dependency.
- No requirement for legal/product strategy/major architectural decision.

### Explicit disqualifier labels / conditions
- Never add `Agent` if existing labels include any of: `Needs-Spec`, `Blocked`, `wontfix`, `epic`, `investigation`, `blocked`, `question`.
- Never add `Agent` when body contains strong external/decision language:
  - `architecture`, `roadmap`, `policy`, `security review`, `legal`, `pricing`, `compliance`, `contract`, `brand decision`, `product decision`, `investigation`.

### `Needs-Spec` application
- If an issue is likely automatable but missing enough detail, add `Needs-Spec` instead of `Agent`.
- Never add `Needs-Spec` to anything already labeled `Agent`.

### Milestone and project-cycle obligations
- If an issue is a strong Agent candidate but has no milestone, assign it to the nearest open milestone when `--auto-assign-milestone` is enabled.
- If no suitable open milestone exists, post a planning alert in comments/summaries.
- Inspect project health via `gh project` and flag empty/closed project boards and missing active planning context.
- Raise alerts when nearest milestone due dates are nearing (`--project-alert-days`) or overdue.
- Surface planning risks where upcoming cycles should be planned immediately.

## Script entry point
`scripts/label_agent_issues.py`

### Main arguments
- `--root` workspace root used for local repository discovery (default `.`)
- `--repo` explicit `owner/repo` override (single repo)
- `--label` label to apply for automatable issues (default `Agent`)
- `--needs-spec-label` label for underspecified issues (default `Needs-Spec`)
- `--threshold` confidence threshold for `Agent` (0-100)
- `--apply` performs writes; without it, runs read-only mode
- `--max-issues` max open issues checked per repo (default 150)
- `--json` machine-readable output
- `--apply-needs-spec` applies `Needs-Spec` on medium-confidence issues
- `--apply-comments` posts comments with `@`-mentions for clarification/planning gaps
- `--auto-assign-milestone` auto-assigns the recommended open milestone to strong Agent candidates
- `--project-alert-days` when to raise milestone cycle alerts ahead of due date
- `--label-color`, `--needs-spec-color`, and corresponding descriptions can be customized

### Project mutation expectation
- This skill audits project visibility/health but does not currently create, edit, or move GitHub project items.
- Project checks are best-effort and skip with a clear alert when `gh project` is unavailable or not permitted in the current context.

## Required behavior for GitHub operations
- All reads and writes must use `gh` commands.
- Do not use manual web UI clicks for labeling, milestone assignment, or project inspection.
- Keep actions auditable: output what changed.

### Expected outputs for this skill
- Per issue summary includes:
  - decision (`agent`, `needs_spec`, `skip`, `already_agent`, `investigate`)
  - confidence score
  - milestone missing state
  - clarification-needed state
- Planning section includes:
  - milestone gap alerts
  - project view warnings
  - cycle alerts when milestones near/overdue
- Final report groups issues by repository and prints Markdown links to each issue.
- All human-attention items (`needs-spec`, `skip`, `investigate`, missing milestone, clarification needed) are emitted last in a dedicated:
  - `Immediate attention required`
  - each entry includes a link and actionable next steps
- `investigate` entries should include:
  - duplicate/fix history checks
  - linked PR/issue cross-checking
  - explicit recommendation: close, relabel, or continue backlog

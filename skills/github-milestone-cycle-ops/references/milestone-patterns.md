# Milestone Patterns

## Naming Convention

Use one shared milestone name across all repos in the same project:

`<ProjectShort>-M<NN>-<Outcome>-<YYYY-MM-DD>`

Examples:
- `ProjectAlpha-M03-Beta-Activation-2026-03-31`
- `ProjectBeta-M02-Revenue-Reactivation-2026-03-21`
- `ProjectGamma-M09-Handoff-Completion-2026-03-17`

## Milestone Definition of Done (DoD)

Write DoD as outcomes:

1. Observable business or delivery result
2. Measurable threshold or acceptance condition
3. Operational readiness condition

Template:

```text
DoD:
- Users/partners can complete <core flow> with no blocking defects.
- Metric threshold: <metric> >= <target> over <window>.
- Operations: <automation/runbook/monitoring> is active and verified.
```

## Current + Next Milestone Policy

1. Keep only one active execution milestone per project.
2. Keep one pre-shaped next milestone with draft issue candidates.
3. Move unfinished work forward only if it still fits the outcome; otherwise close or re-scope.

## Multi-Repo Rules

1. Same milestone title and due date in each repo.
2. Every in-scope issue in every repo must map to this milestone.
3. If one repo lags, rebalance scope; do not silently drift milestone dates.

## Anti-Patterns

1. Milestones named by engineering tasks only.
2. Milestones with no metric or outcome.
3. Different milestone names for repos in the same project cycle.
4. Carrying vague `Needs-Spec` issues inside active milestone scope.

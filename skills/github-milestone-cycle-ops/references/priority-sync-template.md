# Priority Sync Template

Use this template to align human and AI priorities before cycle execution.

## Canonical Path

`$PORTFOLIO_ROOT/operator/daily_notes/priority-sync/<YYYY-MM-DD>-portfolio-priority-sync.md`

Optional convenience copy:

`$PORTFOLIO_ROOT/operator/daily_notes/priority-sync/latest.md`

## Required Structure

```markdown
# Portfolio Priority Sync

Date: <YYYY-MM-DD>
Valid Until: <YYYY-MM-DD>   # usually +7 days
Author: <name>

## Portfolio Direction
- Primary objective this cycle: <text>
- Secondary objective: <text>
- Non-goals: <text>
- Risk posture: speed-first | balanced | quality-first

## Project Priorities

### <project-slug>
- Human priority:
  - P1: <outcome>
  - P2: <outcome>
  - P3: <outcome>
- AI recommendation:
  - P1: <outcome>
  - P2: <outcome>
  - P3: <outcome>
- Decision:
  - chosen_order: <final ordered list>
  - reason: <short reason>
  - constraints: <limits/guardrails>

## Cycle Loading Rules
- Max planned load: <e.g., 80%>
- Minimum per active project: 1 in-progress + 2 queued AI-ready issues
- Freeze rules: <what cannot be changed this cycle>

## Execution Overrides
- <explicit issue/repo priorities or de-priorities>
```

## Usage Rules

1. Prefer this artifact over inferred priorities when available.
2. If this file is missing or stale (>7 days), run in conservative mode.
3. Include the exact path/date of the loaded sync file in final output and write-back JSON.

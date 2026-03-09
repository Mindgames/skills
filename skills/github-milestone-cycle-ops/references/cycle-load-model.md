# Cycle Load Model

Use this model to avoid underloading or overloading milestones.

## Inputs

1. Cycle duration (days)
2. Human availability (hours)
3. Agent throughput estimate (issues/day or effort units/day)
4. Review/integration overhead (hours)
5. Interrupt reserve (percentage)

## Effort Mapping

Use this default if no project-specific calibration exists:

- `XS` = 1 hour
- `S` = 2 hours
- `M` = 4 hours
- `L` = 8 hours

Adjust per team history when data exists.

## Capacity Formula

`realistic_capacity = (human_hours + agent_equivalent_hours) - review_overhead`

`planned_capacity = realistic_capacity * 0.70 to 0.85`

Keep remaining `15-30%` as slack.

## Portfolio Load Split

Apply target split:

1. `60%` core value (revenue/users/critical shipping)
2. `30%` enablers (automation/reliability/debt blocking velocity)
3. `10%` option value (R&D or speculative bets)

## Minimum Active Project Load

Every active project should keep:

1. 1 milestone-critical issue in progress
2. 2 AI-ready queued issues

This keeps distributed agents productive and prevents idle projects.

## Replanning Triggers

Replan immediately when:

1. Open blockers consume >20% of cycle capacity
2. PR review queue exceeds 2 days average wait
3. Critical dependency slips beyond 3 days
4. Top metric trend drops for two consecutive reviews

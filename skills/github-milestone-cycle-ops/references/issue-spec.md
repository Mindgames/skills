# AI-Ready Issue Spec

Use this format for issues that should be executable by agents.

## Required Sections

```markdown
## Goal
<What outcome must be achieved and why it matters now>

## Scope
- In: <explicit in-scope work>
- Out: <guardrails>

## Acceptance Criteria
- [ ] <testable criterion 1>
- [ ] <testable criterion 2>
- [ ] <testable criterion 3>

## Implementation Notes
- Constraints: <tech/process constraints>
- Dependencies: <issues/PRs/services>
- Risks: <known risks and mitigation>

## Delivery Metadata
- Impact: H|M|L
- Effort: XS|S|M|L
- Owner Mode: Agent|Human|Hybrid
- Milestone: <milestone name>
```

## Label Policy

1. `Agent`: scope is clear enough for autonomous implementation.
2. `Needs-Spec`: scope is ambiguous or acceptance criteria are missing.
3. `Blocked`: dependency outside team control.

## Quality Checks Before Marking `Agent`

1. Issue has explicit acceptance criteria.
2. Dependencies are listed and reachable.
3. Scope is small enough to complete within one cycle slice.
4. Reviewer path is clear.

## Splitting Rule

Split an issue if any are true:

1. Multiple unrelated acceptance criteria.
2. Expected effort > `L` or >1 sprint/cycle slice.
3. Cross-repo work without clear sequencing.

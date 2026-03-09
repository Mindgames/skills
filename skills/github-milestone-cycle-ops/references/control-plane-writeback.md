# control-plane Write-Back Contract

Use this contract at the end of each milestone/cycle planning run.

## Path Rules

1. Preferred root: `$PORTFOLIO_ROOT`
2. If missing, fallback root: `<repo-root>/.codex/reports/milestone-cycle-sync`

## Output Files

For date `YYYY-MM-DD` and project slug `<slug>`:

1. Markdown:
   - `<root>/operator/daily_notes/project-cycle-sync/<YYYY-MM-DD>-<slug>-milestone-cycle-sync.md`
2. JSON:
   - `<root>/operator/daily_notes/project-cycle-sync/<YYYY-MM-DD>-<slug>-milestone-cycle-sync.json`

Use parent project slug for `<slug>` when a parent project exists (for example `project-alpha`, not `project-alpha-web`).

Fallback layout:

1. `<fallback-root>/<YYYY-MM-DD>-<slug>-milestone-cycle-sync.md`
2. `<fallback-root>/<YYYY-MM-DD>-<slug>-milestone-cycle-sync.json`

## Markdown Structure

```markdown
# Milestone Cycle Sync

Date: <YYYY-MM-DD>
Project: <slug>
Repo Scope: <repo list>
Priority Sync Source: <absolute path>
Priority Sync Date: <YYYY-MM-DD>
Priority Sync Fresh: yes|no

## Milestones
- Current: <name> (target: <date>)
- Current DoD: <text>
- Next: <name> (target: <date>)
- Next DoD: <text>

## Cycle Load
- Realistic capacity: <value>
- Planned load: <value>
- Slack: <value>
- Split: core=<%> enabler=<%> option=<%>

## GitHub Changes
- Milestones created/updated: <list with full links>
- Issues created/updated: <list with full links>
- Labels changed: <list with full links where relevant>
- Board updates: <list with full links>

## Risks
- <risk> :: mitigation=<plan> :: owner=<owner>

## Next Actions
- [ ] <action> :: owner_mode=Agent|Human|Hybrid :: due=<YYYY-MM-DD> :: link=<full URL> :: done_when=<testable outcome>
```

## JSON Schema

```json
{
  "date": "YYYY-MM-DD",
  "project_slug": "string",
  "repos": ["owner/repo"],
  "priority_sync": {
    "source_path": "/abs/path.md",
    "source_date": "YYYY-MM-DD",
    "fresh": "boolean",
    "human_priorities": ["string"],
    "ai_priorities": ["string"],
    "resolved_conflicts": ["string"]
  },
  "milestones": {
    "current": { "name": "string", "target": "YYYY-MM-DD", "dod": "string" },
    "next": { "name": "string", "target": "YYYY-MM-DD", "dod": "string" }
  },
  "cycle_load": {
    "realistic_capacity": "number|string",
    "planned_load": "number|string",
    "slack": "number|string",
    "split": { "core": "number", "enabler": "number", "option": "number" }
  },
  "github_changes": {
    "milestones": ["string"],
    "issues": ["string"],
    "labels": ["string"],
    "board_updates": ["string"]
  },
  "risks": [
    { "risk": "string", "mitigation": "string", "owner": "string" }
  ],
  "next_actions": [
    {
      "title": "string",
      "owner_mode": "Agent|Human|Hybrid",
      "due": "YYYY-MM-DD",
      "link": "https://...",
      "done_when": "string"
    }
  ]
}
```

## Completion Gate

A planning run is not complete until write-back files are written successfully.

#!/usr/bin/env python3
"""Scan open GitHub issues and label candidate issues as Agent or Needs-Spec."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKIP_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    "target",
    ".pytest_cache",
    ".terraform",
    ".cache",
    "coverage",
}

POSITIVE_TERMS = {
    "bug",
    "fix",
    "add",
    "create",
    "implement",
    "update",
    "remove",
    "improve",
    "refactor",
    "document",
    "docs",
    "test",
    "error",
    "failure",
    "regression",
    "timeout",
    "crash",
    "lint",
    "ci",
}

EXPLICIT_CONTEXT_HINTS = {
    "acceptance",
    "expected",
    "steps to reproduce",
    "how to reproduce",
    "repro",
    "given",
    "when",
    "then",
    "criteria",
    "unit tests",
    "integration tests",
}

EXCLUSION_TERMS = {
    "architecture",
    "roadmap",
    "policy",
    "legal",
    "pricing",
    "compliance",
    "product decision",
    "strategy",
    "brand",
    "investigation",
    "spike",
    "research",
    "design",
    "approval",
}

BLOCK_LABELS = {
    "needs-spec",
    "needs spec",
    "blocked",
    "wontfix",
    "epic",
    "question",
}

QUESTION_TRIGGER = re.compile(r"\?|needs more info|missing information|clarif", re.IGNORECASE)
INVESTIGATION_HINTS = [
    "docbuild",
    "docs build",
    "build failed",
    "already fixed",
    "fixed in",
    "resolved",
    "duplicate",
    "duplicates",
    "same as",
    "closed by",
    "merged",
    "works now",
    "was fixed",
    "succeeded",
]


@dataclass
class IssueResult:
    repo: str
    number: int
    title: str
    url: str
    score: int
    decision: str
    reasons: list[str]
    needs_input: bool
    needs_milestone: bool
    author: str | None = None
    milestone_title: str | None = None


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        text=True,
        capture_output=True,
    )


def run_gh_json(cmd: list[str], cwd: Path) -> Any:
    result = run(cmd, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse gh JSON output: {exc}")


def ensure_gh_auth(repo: str, repo_path: Path) -> None:
    auth = run(["gh", "auth", "status"], cwd=repo_path)
    if auth.returncode != 0:
        raise RuntimeError("gh auth is required. Run `gh auth login` first.")

    check = run(["gh", "repo", "view", repo], cwd=repo_path)
    if check.returncode != 0:
        raise RuntimeError(f"No access to {repo} from {repo_path}")


def discover_repos(root: Path) -> list[tuple[str, Path]]:
    repos: list[tuple[str, Path]] = []
    seen = set()

    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        current = Path(dirpath).resolve()
        if (current / ".git").is_dir():
            toplevel = run(["git", "rev-parse", "--show-toplevel"], cwd=current)
            if toplevel.returncode != 0:
                dirnames[:] = [d for d in dirnames if d != ".git"]
                continue

            repo_root = Path(toplevel.stdout.strip()).resolve()
            payload = run_gh_json(["gh", "repo", "view", "--json", "nameWithOwner"], repo_root)
            repo_name = payload.get("nameWithOwner")
            if not repo_name:
                dirnames[:] = [d for d in dirnames if d != ".git"]
                continue

            if repo_name not in seen:
                seen.add(repo_name)
                repos.append((str(repo_name), repo_root))
            dirnames[:] = [d for d in dirnames if d != ".git"]

    return repos


def issue_labels(issue: dict[str, Any]) -> set[str]:
    labels = issue.get("labels") or []
    return {str(label.get("name", "")).strip().lower() for label in labels if label.get("name")}


def label_exists(repo: str, repo_path: Path, name: str, color: str, description: str) -> None:
    payload = run_gh_json(["gh", "label", "list", "--repo", repo, "--json", "name"], repo_path)
    existing = {str(item.get("name", "")).strip() for item in payload}
    if name in existing:
        return

    result = run(
        [
            "gh",
            "label",
            "create",
            name,
            "--repo",
            repo,
            "--color",
            color,
            "--description",
            description,
        ],
        cwd=repo_path,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed creating label `{name}` in {repo}: {result.stderr.strip() or result.stdout.strip()}"
        )


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_open_milestones(repo: str, repo_path: Path) -> list[dict[str, Any]]:
    try:
        payload = run_gh_json(
            [
                "gh",
                "api",
                f"repos/{repo}/milestones",
                "-f",
                "state=open",
                "-f",
                "sort=due_on",
                "-f",
                "direction=asc",
                "--method",
                "GET",
                "--paginate",
            ],
            cwd=repo_path,
        )
    except RuntimeError:
        payload = run_gh_json(
            [
                "gh",
                "api",
                f"repos/{repo}/milestones",
                "-f",
                "state=open",
                "--method",
                "GET",
                "--paginate",
            ],
            cwd=repo_path,
        )

    if isinstance(payload, dict):
        # In rare cases gh may return keyed output.
        payload = list(payload.values())

    return payload if isinstance(payload, list) else []


def evaluate_milestones(repo: str, milestones: list[dict[str, Any]], alert_days: int) -> tuple[list[str], str | None]:
    alerts: list[str] = []
    recommended = None

    if not milestones:
        return [f"{repo}: no open milestones found; cycle planning needed"], None

    now = datetime.now(timezone.utc)
    nearest_due: datetime | None = None
    for milestone in milestones:
        due_on = parse_datetime(milestone.get("due_on"))
        if due_on is None:
            continue
        if nearest_due is None or due_on < nearest_due:
            nearest_due = due_on
            recommended = milestone.get("title")

    if nearest_due is not None:
        days_left = (nearest_due.date() - now.date()).days
        if days_left <= 0:
            alerts.append(f"{repo}: nearest open milestone `{recommended}` is due now/overdue; plan next cycle immediately")
        elif days_left <= alert_days:
            alerts.append(
                f"{repo}: nearest open milestone `{recommended}` is due in {days_left} day(s); plan upcoming cycle"
            )

    return alerts, recommended


def evaluate_repo_projects(owner: str, repo: str, repo_path: Path) -> list[str]:
    alerts: list[str] = []
    try:
        projects = run_gh_json(
            ["gh", "project", "list", "--owner", owner, "--json", "number,title,closed,updatedAt", "--limit", "50"],
            cwd=repo_path,
        )
    except RuntimeError:
        return [f"{repo}: project view inspection unavailable via gh project list"]

    if not projects:
        alerts.append(f"{repo}: no GitHub projects found for {owner}")
        return alerts

    open_projects = [item for item in projects if not item.get("closed")]
    if not open_projects:
        alerts.append(f"{repo}: all projects are closed; triage context may be incomplete")
        return alerts

    for project in open_projects:
        number = project.get("number")
        if not number:
            continue

        project_name = str(project.get("title", f"Project {number}"))
        try:
            items = run_gh_json(
                [
                    "gh",
                    "project",
                    "item-list",
                    str(number),
                    "--owner",
                    owner,
                    "--limit",
                    "1",
                    "--json",
                    "id",
                ],
                cwd=repo_path,
            )
        except RuntimeError:
            alerts.append(
                f"{repo}: unable to inspect items for project `{project_name}` (use project dashboard to verify cycle fields)"
            )
            continue

        if isinstance(items, list):
            if not items:
                alerts.append(f"{repo}: project `{project_name}` appears empty; check whether active items are missing")
            continue

        if isinstance(items, dict):
            nodes = items.get("nodes", [])
            if not nodes:
                alerts.append(f"{repo}: project `{project_name}` appears empty; check whether active items are missing")

    return alerts


def choose_default_milestone(milestones: list[dict[str, Any]]) -> str | None:
    for milestone in milestones:
        due_on = parse_datetime(milestone.get("due_on"))
        if due_on:
            return milestone.get("title")
    if milestones:
        return milestones[0].get("title")
    return None


def score_issue(issue: dict[str, Any]) -> tuple[int, list[str]]:
    score = 40
    reasons: list[str] = []

    title = (issue.get("title") or "").strip()
    body = (issue.get("body") or "").strip()
    combined = f"{title} {body}".lower()

    if not body:
        score -= 10
        reasons.append("Missing issue body")

    title_tokens = set(re.findall(r"[a-zA-Z0-9#+-]+", title.lower()))
    positive_hits = len(POSITIVE_TERMS.intersection(title_tokens))
    if positive_hits:
        score += positive_hits * 10
        reasons.append(f"Title contains implementation verbs ({positive_hits})")

    context_hits = sum(1 for marker in EXPLICIT_CONTEXT_HINTS if marker in combined)
    if context_hits:
        score += context_hits * 8
        reasons.append("Contains reproducibility/acceptance context")

    if "```" in body or "`" in body:
        score += 6
        reasons.append("Contains code/reference blocks")

    if re.search(r"\b(steps|expected|actual|acceptance)\b", combined):
        score += 8
        reasons.append("Describes expected behavior")

    for bad in EXCLUSION_TERMS:
        if bad in combined:
            score -= 14
            reasons.append(f"Contains exclusion language: {bad}")

    if re.search(
        r"\b(external api|external service|third[- ]party|oauth|credential|pci|legal|contract|pricing|go-to-market)\b",
        combined,
    ):
        score -= 18
        reasons.append("High external dependency or decision risk")

    if len(body) < 60:
        score -= 12
        reasons.append("Body too short for reliable scoping")

    if score < 0:
        score = 0
    elif score > 100:
        score = 100

    return score, reasons


def extract_author(issue: dict[str, Any]) -> str | None:
    author = issue.get("author") or {}
    return author.get("login") if isinstance(author, dict) else None


def evaluate_issue(
    repo: str,
    issue: dict[str, Any],
    threshold: int,
    apply_needs_spec: bool,
) -> IssueResult:
    labels = issue_labels(issue)
    number = issue["number"]
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    combined = f"{title} {body}".strip()
    url = str(issue.get("url") or "")

    milestone = issue.get("milestone")
    milestone_title = milestone.get("title") if isinstance(milestone, dict) else None

    needs_input = bool(QUESTION_TRIGGER.search(combined)) or len(combined) < 45
    needs_milestone = milestone is None
    investigation_hint = any(hint in combined.lower() for hint in INVESTIGATION_HINTS)

    if labels.intersection(BLOCK_LABELS):
        return IssueResult(
            repo=repo,
            number=number,
            title=title,
            url=url,
            score=0,
            decision="skip",
            reasons=["Blocked or non-spec label detected"],
            needs_input=needs_input,
            needs_milestone=needs_milestone,
            author=extract_author(issue),
            milestone_title=milestone_title,
        )

    if "agent" in labels and "needs-spec" not in labels:
        return IssueResult(
            repo=repo,
            number=number,
            title=title,
            url=url,
            score=100,
            decision="already_agent",
            reasons=["Already labeled Agent"],
            needs_input=needs_input,
            needs_milestone=needs_milestone,
            author=extract_author(issue),
            milestone_title=milestone_title,
        )

    score, reasons = score_issue(issue)

    if needs_input:
        reasons.append("Contains question markers or insufficient scoping detail")

    if investigation_hint:
        reasons.append("Issue appears to reference duplicate/fix context and needs manual investigation.")

    if investigation_hint:
        decision = "investigate"
    elif not needs_input and score >= threshold:
        decision = "agent"
    elif apply_needs_spec and score >= 45:
        decision = "needs_spec"
    else:
        decision = "skip"

    return IssueResult(
        repo=repo,
        number=number,
        title=title,
        url=url,
        score=score,
        decision=decision,
        reasons=reasons,
        needs_input=needs_input,
        needs_milestone=needs_milestone,
        author=extract_author(issue),
        milestone_title=milestone_title,
    )


def list_open_issues(repo: str, repo_path: Path, max_issues: int) -> list[dict[str, Any]]:
    payload = run_gh_json(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            str(max_issues),
            "--json",
            "number,title,body,labels,url,author,milestone",
        ],
        repo_path,
    )

    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected gh issue list payload for {repo}: {payload!r}")

    return payload


def comment_issue(
    repo: str,
    repo_path: Path,
    issue: IssueResult,
    milestone_recommendation: str | None,
    project_alerts: list[str],
) -> None:
    mentions = [f"@{issue.author}"] if issue.author else []
    if not mentions:
        return

    message = []
    message.append(", ".join(mentions) + ",")

    if issue.needs_input:
        message.append(
            "This issue appears to need follow-up clarification before Agent handoff."
            " Please add concrete acceptance criteria, reproducible steps, and expected/actual behavior."
        )

    if issue.decision == "investigate":
        message.append(
            "This issue is likely tied to prior fixes/duplicates and requires manual verification before"
            " Agent handoff. Check linked PR history and whether the reported failure is still reproducible."
        )

    if issue.needs_milestone:
        if milestone_recommendation:
            message.append(f"This issue is unplanned and should be assigned to milestone `{milestone_recommendation}`.")
        else:
            message.append("This issue is unplanned and has no open milestones assigned.")

    if project_alerts:
        message.append(
            "Project cycle check: " + "; ".join([item.split(":", 1)[1].strip() for item in project_alerts[:1]])
        )

    if not message:
        return

    comment_body = "\n\n".join(message)
    run([
        "gh",
        "issue",
        "comment",
        str(issue.number),
        "--repo",
        repo,
        "--body",
        comment_body,
    ], cwd=repo_path)


def issue_markdown_link(issue: IssueResult) -> str:
    url = issue.url
    if not url.startswith("http"):
        url = f"https://github.com/{issue.repo}/issues/{issue.number}"
    return f"[#{issue.number}]({url})"


def issue_requires_attention(issue: IssueResult) -> bool:
    return issue.needs_input or issue.decision in {"needs_spec", "skip", "investigate"} or issue.needs_milestone


def issue_attention_actions(issue: IssueResult, recommended_milestone: str | None) -> list[str]:
    actions: list[str] = []
    if issue.needs_input:
        actions.append(
            "Needs clarification: add concrete acceptance criteria, expected/actual behavior, and reproducible steps."
        )
    if issue.needs_milestone:
        if recommended_milestone:
            actions.append(
                f"Assign an open milestone (recommended: `{recommended_milestone}`) before handing off."
            )
        else:
            actions.append("No open milestone available; assign/plan a milestone before handoff.")
    if issue.decision == "needs_spec":
        actions.append("Re-scope or expand implementation details so it can be labeled Agent.")
    if issue.decision == "investigate":
        actions.append(
            "Verify if issue is already fixed/duplicate by checking linked PRs and CI outcomes before deciding close vs keep open."
        )
    if issue.decision == "skip":
        actions.append("Manual review needed for non-automatable or policy/architecture-sensitive context.")
    if issue.decision == "already_agent" and not actions:
        actions.append("Re-check planning fields; issue is already marked Agent.")
    if not actions:
        actions.append("Manual decision needed from maintainer.")
    return actions


def assign_milestone(repo: str, repo_path: Path, issue: IssueResult, milestone_title: str) -> bool:
    result = run(
        [
            "gh",
            "issue",
            "edit",
            str(issue.number),
            "--repo",
            repo,
            "--milestone",
            str(milestone_title),
        ],
        cwd=repo_path,
    )
    return result.returncode == 0


def run_label_workflow(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if not root.exists():
        raise RuntimeError(f"Root path does not exist: {root}")

    if args.repo:
        if (root / ".git").is_dir():
            payload = run_gh_json(["gh", "repo", "view", "--json", "nameWithOwner"], root)
            resolved_repo = payload.get("nameWithOwner")
            repos = [(resolved_repo, root)] if resolved_repo else [(args.repo, root)]
        else:
            repos = [(args.repo, Path.cwd())]
    else:
        repos = discover_repos(root)

    if not repos:
        raise RuntimeError("No local repositories discovered. Set --repo explicitly if needed.")

    results: list[IssueResult] = []
    repo_alerts_map: dict[str, list[str]] = {}
    milestone_recommendation: dict[str, str | None] = {}

    for repo, repo_path in repos:
        ensure_gh_auth(repo, repo_path)

        owner = repo.split("/")[0]
        repo_alerts: list[str] = []
        alerts: list[str] = []

        try:
            milestones = fetch_open_milestones(repo, repo_path)
            milestone_alerts, recommended = evaluate_milestones(repo, milestones, args.project_alert_days)
            alerts.extend(milestone_alerts)
            milestone_recommendation[repo] = recommended
        except RuntimeError as exc:
            alerts.append(f"{repo}: unable to read milestones via gh API ({exc})")
            milestones = []
            milestone_recommendation[repo] = None

        try:
            alerts.extend(evaluate_repo_projects(owner, repo, repo_path))
        except RuntimeError as exc:
            alerts.append(f"{repo}: project inspection failed ({exc})")

        repo_alerts_map[repo] = alerts

        label_exists(repo, repo_path, args.label, args.label_color, args.label_description)
        label_exists(
            repo,
            repo_path,
            args.needs_spec_label,
            args.needs_spec_color,
            args.needs_spec_description,
        )

        issues = list_open_issues(repo, repo_path, args.max_issues)
        for issue in issues:
            evaluation = evaluate_issue(repo=repo, issue=issue, threshold=args.threshold, apply_needs_spec=args.apply_needs_spec)
            results.append(evaluation)

            if evaluation.decision == "already_agent":
                if (not evaluation.needs_milestone and not evaluation.needs_input) or not args.apply:
                    pass
            if not args.apply:
                continue

            if evaluation.decision == "agent":
                run(
                    [
                        "gh",
                        "issue",
                        "edit",
                        str(evaluation.number),
                        "--repo",
                        repo,
                        "--add-label",
                        args.label,
                    ],
                    cwd=repo_path,
                )

                if evaluation.needs_milestone and args.auto_assign_milestone:
                    recommended_milestone = milestone_recommendation.get(repo)
                    if recommended_milestone:
                        if not assign_milestone(repo, repo_path, evaluation, recommended_milestone):
                            alerts.append(f"{repo}: couldn't assign `{args.label}` issue #{evaluation.number} to milestone `{recommended_milestone}`")
                    else:
                        alerts.append(f"{repo}: couldn't auto-assign milestone for issue #{evaluation.number}; none available")

                if args.apply_comments:
                    if evaluation.needs_input or evaluation.needs_milestone:
                        comment_issue(repo, repo_path, evaluation, milestone_recommendation.get(repo), repo_alerts)

            elif evaluation.decision == "needs_spec" and args.apply_needs_spec:
                run(
                    [
                        "gh",
                        "issue",
                        "edit",
                        str(evaluation.number),
                        "--repo",
                        repo,
                        "--add-label",
                        args.needs_spec_label,
                    ],
                    cwd=repo_path,
                )
                if args.apply_comments and (evaluation.needs_input or evaluation.needs_milestone):
                    comment_issue(repo, repo_path, evaluation, milestone_recommendation.get(repo), repo_alerts)
            elif evaluation.decision == "investigate" and args.apply_comments:
                comment_issue(repo, repo_path, evaluation, milestone_recommendation.get(repo), repo_alerts)
            elif evaluation.needs_input and args.apply_comments:
                comment_issue(repo, repo_path, evaluation, milestone_recommendation.get(repo), repo_alerts)
            elif evaluation.needs_milestone and args.apply and args.auto_assign_milestone is False:
                alerts.append(f"{repo}: issue #{evaluation.number} missing milestone and was not auto-assigned")

    if args.json:
        payload = [r.__dict__ | {"author": r.author, "milestone": r.milestone_title} for r in results]
        print(json.dumps(payload, indent=2))
        return 0

    by_repo: dict[str, list[IssueResult]] = {}
    attention_by_repo: dict[str, list[IssueResult]] = {}
    for result in results:
        if issue_requires_attention(result):
            attention_by_repo.setdefault(result.repo, []).append(result)
        else:
            by_repo.setdefault(result.repo, []).append(result)

    for repo, items in by_repo.items():
        print(f"\n## {repo}")
        print("-" * len(repo))
        for item in items:
            print(f"- {issue_markdown_link(item)} [{item.decision}] {item.score:>3}%")
            print(f"  {item.title}")
            if item.milestone_title:
                print(f"  Milestone: {item.milestone_title}")
            else:
                print("  Milestone: unplanned")
            for reason in item.reasons:
                print(f"  - {reason}")

        if repo_alerts_map.get(repo):
            print("\n  Alerts:")
            for alert in repo_alerts_map[repo]:
                print(f"  ! {alert}")

    applied_agent = sum(1 for item in results if item.decision == "agent")
    applied_investigates = sum(1 for item in results if item.decision == "investigate")
    applied_needs_spec = sum(1 for item in results if item.decision == "needs_spec")
    need_input = sum(1 for item in results if item.needs_input)
    missing_milestone = sum(1 for item in results if item.needs_milestone)

    print(
        f"\nSummary: agent={applied_agent}, investigate={applied_investigates}, needs-spec={applied_needs_spec},"
        f" need-input={need_input}, missing-milestone={missing_milestone}"
    )

    if repo_alerts_map:
        print("\nPlanning alerts:")
        for alerts in repo_alerts_map.values():
            for alert in alerts:
                print(f"- {alert}")

    if attention_by_repo:
        print("\n## Immediate attention required")
        for repo, items in attention_by_repo.items():
            print(f"\n### {repo}")
            for item in items:
                print(f"- {issue_markdown_link(item)} ({item.decision}, score={item.score}):")
                for action in issue_attention_actions(item, milestone_recommendation.get(repo)):
                    print(f"  - {action}")
                for reason in item.reasons:
                    print(f"  - Context: {reason}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Label GitHub issues suitable for Agent workflow")
    parser.add_argument("--root", default=".", help="Workspace root to discover local repos")
    parser.add_argument("--repo", help="Optional owner/repo to limit to one repository")
    parser.add_argument("--label", default="Agent", help="Label name for confidently automatable issues")
    parser.add_argument("--label-color", default="0E8A16", help="Color used when creating the Agent label")
    parser.add_argument(
        "--label-description",
        default="Issue is well-scoped for autonomous agent execution",
        help="Description when creating Agent label",
    )
    parser.add_argument("--needs-spec-label", default="Needs-Spec", help="Label for uncertain issues")
    parser.add_argument("--needs-spec-color", default="FBCA04", help="Color used when creating Needs-Spec label")
    parser.add_argument(
        "--needs-spec-description",
        default="Missing acceptance details for autonomous execution",
        help="Description when creating Needs-Spec label",
    )
    parser.add_argument("--threshold", type=int, default=78, help="Minimum confidence score for Agent labeling")
    parser.add_argument("--max-issues", type=int, default=150, help="Max open issues fetched per repo")
    parser.add_argument("--apply", action="store_true", help="Apply label changes with gh")
    parser.add_argument(
        "--apply-needs-spec",
        action="store_true",
        help="Apply Needs-Spec label for medium-confidence issues",
    )
    parser.add_argument("--apply-comments", action="store_true", help="Post comments with @mentions for clarification/milestone gaps")
    parser.add_argument(
        "--auto-assign-milestone",
        action="store_true",
        help="Auto-assign a recommended open milestone to qualifying Agent issues with no milestone",
    )
    parser.add_argument(
        "--project-alert-days",
        type=int,
        default=14,
        help="How many days before nearest milestone due date to raise cycle planning alert",
    )
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args()
    if args.threshold < 0 or args.threshold > 100:
        raise RuntimeError("--threshold must be between 0 and 100")

    try:
        return run_label_workflow(args)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

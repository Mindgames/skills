#!/usr/bin/env python3
"""Sweep and process Agent-labeled GitHub issues across local repos."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PR_LABEL_APPROVED = "agent-pr/approved"
PR_LABEL_NEEDS_CHANGES = "agent-pr/needs-changes"
PR_LABEL_UNCERTAIN = "agent-pr/uncertain"
ISSUE_LABEL_IN_PROGRESS = "agent/in-progress"
ISSUE_LABEL_RESOLVED = "agent/resolved"
ISSUE_LABEL_BLOCKING = "agent/blocking"

PR_LABELS = {
    "approved": PR_LABEL_APPROVED,
    "needs-changes": PR_LABEL_NEEDS_CHANGES,
    "uncertain": PR_LABEL_UNCERTAIN,
}

ISSUE_LABELS_BY_RESULT = {
    "approved": ISSUE_LABEL_RESOLVED,
    "needs-changes": ISSUE_LABEL_BLOCKING,
    "uncertain": ISSUE_LABEL_BLOCKING,
}

DEFAULT_BRANCH_ALIAS = ["main", "master", "trunk", "develop"]

SKIP_DIRS = {
    ".git",
    ".idea",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "dist",
    "build",
    ".turbo",
    ".cache",
    "target",
    ".pytest_cache",
    "coverage",
    ".terraform",
    "vendor",
}


@dataclass
class RepoIssue:
    repository: str
    number: int
    title: str
    url: str
    updated_at: str | None
    state: str
    labels: list[str]


@dataclass
class RepoMeta:
    name_with_owner: str
    local_path: Path


class ToolError(RuntimeError):
    pass


def _run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ToolError(f"Command not found: {command[0]}") from exc


def _run_json_command(command: list[str], *, cwd: Path | None = None, timeout: int = 120) -> dict[str, Any] | list[Any]:
    process = _run_command(command, cwd=cwd, timeout=timeout)
    if process.returncode != 0:
        raise ToolError(process.stderr.strip() or process.stdout.strip() or "command failed")
    try:
        return json.loads(process.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ToolError(f"failed to parse JSON output: {exc}") from exc


def _normalize_label_value(value: str) -> str:
    return value.strip().lower()


def _parse_labels(payload: Any) -> list[str]:
    labels: list[str] = []
    for item in payload or []:
        if isinstance(item, str):
            labels.append(item)
        elif isinstance(item, dict) and item.get("name"):
            labels.append(str(item["name"]))
    return labels


def _resolve_repo_root(path: Path) -> Path:
    result = _run_command(["git", "rev-parse", "--show-toplevel"], cwd=path)
    if result.returncode != 0:
        raise ToolError(f"not a git repository: {path}")
    return Path(result.stdout.strip()).resolve()


def _ensure_gh_auth(repo_root: Path) -> None:
    auth = _run_command(["gh", "auth", "status"], cwd=repo_root)
    if auth.returncode != 0:
        raise ToolError("gh auth status failed. Run `gh auth login` first.")


def _discover_repos(root: Path) -> list[RepoMeta]:
    discovered: list[RepoMeta] = []
    seen: set[str] = set()

    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]

        marker = Path(dirpath) / ".git"
        if marker.exists():
            candidate = Path(dirpath).resolve()
            if marker.is_file():
                try:
                    candidate = _resolve_repo_root(candidate)
                except ToolError:
                    continue
            repo_root = _resolve_repo_root(candidate)
            repo_key = str(repo_root)
            if repo_key in seen:
                continue
            seen.add(repo_key)

            try:
                repo_name = _run_json_command(
                    ["gh", "repo", "view", "--json", "nameWithOwner"],
                    cwd=repo_root,
                )["nameWithOwner"]
            except ToolError:
                continue

            discovered.append(RepoMeta(name_with_owner=str(repo_name), local_path=repo_root))
            dirnames[:] = [name for name in dirnames if name != ".git"]

    return discovered


def _default_branch(repo_root: Path) -> str:
    payload = _run_json_command(["gh", "repo", "view", "--json", "defaultBranchRef"], cwd=repo_root)
    default_ref = payload.get("defaultBranchRef")
    if isinstance(default_ref, dict):
        name = default_ref.get("name")
        if isinstance(name, str):
            return name

    for fallback in DEFAULT_BRANCH_ALIAS:
        if fallback:
            return fallback
    return "main"


def _issue_ref_from_text(raw: str) -> tuple[str | None, int]:
    text = raw.strip()
    if not text:
        raise ValueError("Issue reference is empty")

    url_match = re.match(r"https?://github\.com/([^/]+/[^/]+)/issues/(\d+)", text)
    if url_match:
        return url_match.group(1), int(url_match.group(2))

    explicit_match = re.match(r"([^/\s]+/[^#\s]+)#(\d+)$", text)
    if explicit_match:
        return explicit_match.group(1), int(explicit_match.group(2))

    numeric_match = re.fullmatch(r"#?(\d+)", text)
    if numeric_match:
        return None, int(numeric_match.group(1))

    raise ValueError(f"unrecognized issue reference: {raw!r}")


def _repo_for_issue(
    repos: list[RepoMeta],
    issue_ref: str,
    fallback_repo: str | None = None,
) -> RepoMeta:
    repo_slug, number = _issue_ref_from_text(issue_ref)

    if repo_slug is None:
        if fallback_repo:
            repo_slug = fallback_repo

        candidates = repos
        if len(candidates) != 1:
            raise ToolError(
                "Issue number alone is ambiguous. Provide `owner/repo#NUMBER` or `--repo`."
            )
        return candidates[0], number

    for repo in repos:
        if repo.name_with_owner.lower() == repo_slug.lower():
            return repo, number

    raise ToolError(f"No local repo matched {repo_slug!r}. Use a matching project under --root.")


def _list_issues(repo: RepoMeta, label: str) -> list[RepoIssue]:
    search_query = f"label:{label} is:open"
    payload = _run_json_command(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo.name_with_owner,
            "--state",
            "open",
            "--search",
            search_query,
            "--json",
            "number,title,url,updatedAt,labels,state",
        ],
        cwd=repo.local_path,
    )

    issues: list[RepoIssue] = []
    for item in payload or []:
        if not isinstance(item, dict):
            continue
        labels = _parse_labels(item.get("labels", []))
        if _normalize_label_value(label) not in {_normalize_label_value(item_label) for item_label in labels}:
            continue

        issues.append(
            RepoIssue(
                repository=repo.name_with_owner,
                number=int(item["number"]),
                title=item.get("title", ""),
                url=item.get("url", ""),
                updated_at=item.get("updatedAt"),
                state=item.get("state", "open"),
                labels=labels,
            )
        )

    issues.sort(key=lambda item: item.updated_at or "")
    return issues


def _collect_agent_issues(root: Path, label: str, project_filter: list[str]) -> list[RepoIssue]:
    repos = _discover_repos(root)
    output: list[RepoIssue] = []
    for repo in repos:
        if project_filter:
            rel = str(repo.local_path.relative_to(root)).replace("\\", "/")
            if not any(
                rel == pf or rel.startswith(f"{pf.rstrip('/')}" + "/") for pf in project_filter
            ):
                continue
        output.extend(_list_issues(repo, label))
    return output


def _safe_branch_suffix(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned[:60] or "issue"


def _branch_exists(repo_root: Path, branch: str) -> bool:
    return _run_command(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo_root).returncode == 0


def _remote_branch_exists(repo_root: Path, branch: str) -> bool:
    result = _run_command(["git", "ls-remote", "--heads", "origin", branch], cwd=repo_root)
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def _ensure_issue_labels(repo: RepoMeta, number: int, labels: list[str]) -> None:
    for label in labels:
        color = "6f42c1" if "progress" in label else "0e8a16"
        ensure = _run_command(
            [
                "gh",
                "label",
                "create",
                label,
                "--color",
                color,
                "--description",
                "Managed by Github Process Agent Issues",
                "--repo",
                repo.name_with_owner,
            ],
            cwd=repo.local_path,
        )
        if ensure.returncode != 0:
            stderr = (ensure.stderr or "").lower()
            if "already exists" not in stderr:
                stdout = (ensure.stdout or "").lower()
                if "already exists" not in stdout:
                    raise ToolError(f"cannot ensure label {label!r}: {ensure.stderr.strip() or ensure.stdout.strip()}")

    _run_command(
        ["gh", "issue", "edit", str(number), "--repo", repo.name_with_owner, "--add-label", ",".join(labels)],
        cwd=repo.local_path,
    )


def _comment_issue(repo: RepoMeta, number: int, body: str) -> None:
    _run_command(
        [
            "gh",
            "issue",
            "comment",
            str(number),
            "--repo",
            repo.name_with_owner,
            "--body",
            body,
        ],
        cwd=repo.local_path,
    )


def _comment_pr(repo: RepoMeta, pr_number: int, body: str) -> None:
    _run_command(
        [
            "gh",
            "pr",
            "comment",
            str(pr_number),
            "--repo",
            repo.name_with_owner,
            "--body",
            body,
        ],
        cwd=repo.local_path,
    )


def _ensure_label(repo: RepoMeta, name: str, color: str, description: str) -> None:
    ensure = _run_command(
        [
            "gh",
            "label",
            "create",
            name,
            "--color",
            color,
            "--description",
            description,
            "--repo",
            repo.name_with_owner,
        ],
        cwd=repo.local_path,
    )
    if ensure.returncode == 0:
        return
    lower = (ensure.stderr or ensure.stdout or "").lower()
    if "already exists" not in lower:
        raise ToolError(f"cannot ensure PR label {name!r}: {ensure.stderr.strip() or ensure.stdout.strip()}")


def _set_pr_labels(repo: RepoMeta, pr_number: int, result: str) -> str:
    target = PR_LABELS[result]
    other = {v for v in PR_LABELS.values() if v != target}

    _ensure_label(
        repo,
        target,
        "0e8a16" if result == "approved" else "d93f0b" if result == "needs-changes" else "8b949e",
        f"Github Process Agent Issues auto-classified as {result}",
    )

    # remove old labels first
    for remove in other:
        _run_command(
            [
                "gh",
                "pr",
                "edit",
                str(pr_number),
                "--repo",
                repo.name_with_owner,
                "--remove-label",
                remove,
            ],
            cwd=repo.local_path,
            timeout=60,
        )

    _run_command(
        [
            "gh",
            "pr",
            "edit",
            str(pr_number),
            "--repo",
            repo.name_with_owner,
            "--add-label",
            target,
        ],
        cwd=repo.local_path,
        timeout=60,
    )
    return target


def _changed_files(repo_root: Path, base_branch: str) -> list[str]:
    diff = _run_command(
        ["git", "diff", "--name-only", f"origin/{base_branch}...HEAD"],
        cwd=repo_root,
        timeout=60,
    )
    if diff.returncode != 0:
        raise ToolError(f"cannot read git diff: {diff.stderr.strip() or diff.stdout.strip()}")
    return [line.strip() for line in diff.stdout.splitlines() if line.strip()]


def _run_syntax_checks(repo_root: Path, files: list[str]) -> list[str]:
    results: list[str] = []
    for rel in files:
        path = repo_root / rel
        if not path.exists() or not path.is_file():
            continue
        if path.suffix == ".py":
            compile_cmd = _run_command([sys.executable, "-m", "compileall", str(path)], cwd=repo_root, timeout=60)
            if compile_cmd.returncode != 0:
                results.append(f"python syntax issue in {rel}")
        elif path.suffix in {".sh", ".bash", ".zsh"}:
            shell_cmd = _run_command(["bash", "-n", str(path)], cwd=repo_root, timeout=60)
            if shell_cmd.returncode != 0:
                results.append(f"shell syntax issue in {rel}")
        elif path.suffix == ".json":
            try:
                with path.open("r", encoding="utf-8") as handle:
                    json.load(handle)
            except Exception as exc:
                results.append(f"invalid JSON in {rel}: {exc}")

    return results


def _run_pytest(repo_root: Path, timeout: int = 600) -> tuple[bool, str]:
    has_pytest = _run_command([sys.executable, "-m", "pytest", "--version"], cwd=repo_root, timeout=30)
    if has_pytest.returncode != 0:
        return False, "pytest unavailable"

    if not (repo_root / "tests").is_dir():
        return False, "no tests directory"

    result = _run_command([sys.executable, "-m", "pytest", "-q"], cwd=repo_root, timeout=timeout)
    if result.returncode != 0:
        return False, (result.stdout + "\n" + result.stderr).strip()[:800]
    return True, ""


def _evaluate(repo_root: Path, base_branch: str, run_tests: bool, pytest_timeout: int) -> tuple[str, int, list[str]]:
    changes = _changed_files(repo_root, base_branch)
    findings: list[str] = []

    if not changes:
        return "needs-changes", 0, ["No diff compared to base branch; nothing to review"]

    findings.extend(_run_syntax_checks(repo_root, changes))

    confidence = 100
    if findings:
        confidence -= 40

    syntax_checked = bool(changes)
    if run_tests:
        passed, details = _run_pytest(repo_root, timeout=pytest_timeout)
        if not passed:
            findings.append(f"pytest failed: {details}")
            confidence -= 30
    else:
        confidence -= 25

    if not syntax_checked:
        confidence -= 15

    if confidence < 0:
        confidence = 0

    if findings:
        verdict = "needs-changes" if any("failed" in item or "invalid" in item or "syntax" in item for item in findings) else "uncertain"
    else:
        verdict = "approved"

    return verdict, confidence, findings


def _open_or_create_branch(repo: RepoMeta, number: int, issue_title: str, base_branch: str | None, push: bool) -> str:
    branch = f"agent/{number}-{_safe_branch_suffix(issue_title)}"
    _run_command(["git", "fetch", "origin"], cwd=repo.local_path, timeout=120)

    resolved_base = base_branch or _default_branch(repo.local_path)
    if not _branch_exists(repo.local_path, branch):
        if _remote_branch_exists(repo.local_path, branch):
            _run_command(["git", "checkout", "-t", "-b", branch, f"origin/{branch}"], cwd=repo.local_path)
        else:
            _run_command(
                ["git", "checkout", "-b", branch, f"origin/{resolved_base}"],
                cwd=repo.local_path,
            )
    else:
        _run_command(["git", "checkout", branch], cwd=repo.local_path)

    if push:
        if _remote_branch_exists(repo.local_path, branch):
            _run_command(["git", "push", "--set-upstream", "origin", branch], cwd=repo.local_path)
        else:
            _run_command(["git", "push", "-u", "origin", branch], cwd=repo.local_path)

    return branch


def _open_or_reuse_pr(
    repo: RepoMeta,
    base_branch: str,
    branch: str,
    title: str,
    body: str,
) -> int:
    existing = _run_json_command(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo.name_with_owner,
            "--state",
            "open",
            "--head",
            branch,
            "--json",
            "number,url",
        ],
        cwd=repo.local_path,
    )

    if existing:
        pr_number = int(existing[0]["number"])
        pr_url = existing[0].get("url", "")
        if pr_url:
            _comment_pr(
                repo,
                pr_number,
                "Issue sweep finalize rerun detected. Reusing existing PR."
            )
        return pr_number

    command = [
        "gh",
        "pr",
        "create",
        "--repo",
        repo.name_with_owner,
        "--head",
        branch,
        "--base",
        base_branch,
        "--title",
        title,
        "--body",
        body,
    ]
    created = _run_command(command, cwd=repo.local_path, timeout=180)
    if created.returncode != 0:
        raise ToolError(created.stderr.strip() or created.stdout.strip() or "failed creating PR")

    inspect_output = _run_json_command(
        ["gh", "pr", "view", "--json", "number,url", "--repo", repo.name_with_owner],
        cwd=repo.local_path,
    )
    return int(inspect_output["number"])


def _find_pr_for_issue(repo: RepoMeta, issue_number: int, branch: str) -> int | None:
    payload = _run_json_command(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo.name_with_owner,
            "--state",
            "open",
            "--head",
            branch,
            "--json",
            "number",
        ],
        cwd=repo.local_path,
    )
    if payload:
        return int(payload[0]["number"])

    linked = _run_json_command(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo.name_with_owner,
            "--state",
            "all",
            "--json",
            "number,title",
        ],
        cwd=repo.local_path,
    )
    needle = f"{issue_number}"
    for item in linked:
        title = str(item.get("title", ""))
        if needle in title:
            return int(item.get("number"))
    return None


def _render_summary(
    action: str,
    issue: RepoIssue,
    branch: str,
    pr_number: int | None,
    result: str | None,
    confidence: int,
    findings: list[str],
) -> dict[str, Any]:
    return {
        "action": action,
        "repository": issue.repository,
        "issue": issue.number,
        "issue_url": issue.url,
        "title": issue.title,
        "branch": branch,
        "pr_number": pr_number,
        "result": result,
        "confidence": confidence,
        "findings": findings,
    }


def command_discover(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if not root.exists():
        raise ToolError(f"root not found: {args.root}")

    issues = _collect_agent_issues(root, args.label, args.project_filter)
    if args.json:
        print(json.dumps([issue.__dict__ for issue in issues], indent=2))
        return 0

    if not issues:
        print(f"No open issues tagged '{args.label}' found under {root}")
        return 0

    for issue in issues:
        labels = ", ".join(issue.labels) if issue.labels else "-"
        updated = issue.updated_at or "-"
        print(f"{issue.repository} #{issue.number}: {issue.title}")
        print(f"  url: {issue.url}")
        print(f"  updated: {updated}")
        print(f"  labels: {labels}")
    return 0


def command_claim(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    repos = _discover_repos(root)
    if not repos:
        raise ToolError(f"No git repos discovered under {root}")

    _ensure_gh_auth(repos[0].local_path)

    repo, issue_number = _repo_for_issue(repos, args.issue, args.repo)
    issue_payload = _run_json_command(
        [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--repo",
            repo.name_with_owner,
            "--json",
            "number,title,state,labels,url",
        ],
        cwd=repo.local_path,
    )
    if issue_payload.get("state") != "OPEN":
        issue_payload_state = issue_payload.get("state")
        if str(issue_payload_state).lower() != "open":
            raise ToolError(f"Issue #{issue_number} in {repo.name_with_owner} is not open")

    labels = _parse_labels(issue_payload.get("labels", []))
    branch = _open_or_create_branch(repo, issue_number, issue_payload.get("title", "issue"), args.base_branch, push=True)

    _ensure_issue_labels(repo, issue_number, [ISSUE_LABEL_IN_PROGRESS])
    _comment_issue(
        repo,
        issue_number,
        (
            "I claimed this issue and am starting work on it. "
            f"Use branch ` {branch} ` and update references here when ready to finalize."
        ),
    )

    issue = RepoIssue(
        repository=repo.name_with_owner,
        number=issue_number,
        title=issue_payload.get("title", ""),
        url=issue_payload.get("url", ""),
        updated_at=None,
        state=issue_payload.get("state", ""),
        labels=labels,
    )

    if args.json:
        print(json.dumps(_render_summary("claim", issue, branch, None, None, 100, []), indent=2))
    else:
        print(f"Claimed {repo.name_with_owner}#{issue_number} on branch {branch}")
    return 0


def command_finalize(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    repos = _discover_repos(root)
    if not repos:
        raise ToolError(f"No git repos discovered under {root}")

    _ensure_gh_auth(repos[0].local_path)

    repo, issue_number = _repo_for_issue(repos, args.issue, args.repo)
    issue_payload = _run_json_command(
        [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--repo",
            repo.name_with_owner,
            "--json",
            "number,title,url,labels,state",
        ],
        cwd=repo.local_path,
    )

    labels = _parse_labels(issue_payload.get("labels", []))
    branch = args.branch or f"agent/{issue_number}-{_safe_branch_suffix(issue_payload.get('title','issue'))}"
    target_result = args.result.lower()
    if target_result not in PR_LABELS:
        raise ToolError(f"invalid result: {target_result}")

    base_branch = args.base_branch or _default_branch(repo.local_path)

    _run_command(["git", "checkout", branch], cwd=repo.local_path)
    _run_command(["git", "pull", "--ff-only", "origin", branch], cwd=repo.local_path, timeout=120)

    verdict, confidence, findings = _evaluate(
        repo.local_path,
        base_branch,
        run_tests=args.run_tests,
        pytest_timeout=args.pytest_timeout,
    )

    result = args.result
    if verdict != result and not args.force_result:
        raise ToolError(
            "Local evaluation and requested final result differ. Use --force-result to override."
            f"\nEvaluation: {verdict} ({confidence}%)"
        )

    if confidence < 100 and not args.allow_low_confidence:
        raise ToolError(
            f"Confidence below required threshold: {confidence}%. "
            "Use --allow-low-confidence only if you accept manual uncertainty."
        )

    pr_body = (
        "## Issue Sweep Finalization\n\n"
        f"- Issue: #{issue_number}\n"
        f"- Result: `{result}`\n"
        f"- Confidence: `{confidence}%`\n"
        "- Findings:\n"
    )
    if findings:
        for item in findings:
            pr_body += f"  - {item}\n"
    else:
        pr_body += "  - none\n"

    pr_title = args.pr_title or f"Fix #{issue_number}: {issue_payload.get('title','')[:70]}"
    pr_url = _run_command([
        "gh",
        "pr",
        "view",
        "--repo",
        repo.name_with_owner,
        "--json",
        "url",
        "--jq",
        ".url",
    ], cwd=repo.local_path)

    try:
        existing = _find_pr_for_issue(repo, issue_number, branch)
        if existing:
            pr_number = existing
        else:
            pr_number = _open_or_reuse_pr(
                repo=repo,
                base_branch=base_branch,
                branch=branch,
                title=pr_title,
                body=pr_body,
            )
    except ToolError:
        # If gh PR create fails because no changes, surface explicit message.
        raise

    pr_info = _run_json_command(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            repo.name_with_owner,
            "--json",
            "url,title",
        ],
        cwd=repo.local_path,
    )

    pr_label = _set_pr_labels(repo, pr_number, result)
    _comment_pr(
        repo,
        pr_number,
        pr_body + f"\nPR classification label: `{pr_label}`",
    )

    _ensure_issue_labels(repo, issue_number, [ISSUE_LABELS_BY_RESULT[result]])
    if ISSUE_LABEL_IN_PROGRESS in labels:
        _run_command(
            [
                "gh",
                "issue",
                "edit",
                str(issue_number),
                "--repo",
                repo.name_with_owner,
                "--remove-label",
                ISSUE_LABEL_IN_PROGRESS,
            ],
            cwd=repo.local_path,
            timeout=60,
        )

    completion_comment = (
        f"Finalized in branch `{branch}` and posted to PR [#{pr_number}]({pr_info.get('url', '')}).\n"
        f"Result: **{result}** with confidence `{confidence}%`"
    )
    _comment_issue(repo, issue_number, completion_comment)

    if result == "approved" and args.close_issue:
        _run_command(
            [
                "gh",
                "issue",
                "close",
                str(issue_number),
                "--repo",
                repo.name_with_owner,
            ],
            cwd=repo.local_path,
            timeout=60,
        )

    issue = RepoIssue(
        repository=repo.name_with_owner,
        number=issue_number,
        title=issue_payload.get("title", ""),
        url=issue_payload.get("url", ""),
        updated_at=None,
        state=issue_payload.get("state", ""),
        labels=labels,
    )

    if args.json:
        print(
            json.dumps(
                _render_summary(
                    "finalize",
                    issue,
                    branch,
                    pr_number,
                    result,
                    confidence,
                    findings,
                ),
                indent=2,
            )
        )
    else:
        print(f"Finalized {repo.name_with_owner}#{issue_number} as {result} in PR #{pr_number}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sweep Agent-labeled issues across local repos.")
    parser.add_argument("--root", default=".", help="Project root to search for git repositories.")
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="List open Agent issues across local repos")
    discover.add_argument("--label", default="Agent", help="Issue label used to queue work")
    discover.add_argument("--project-filter", action="append", default=[], help="Limit output to matching path prefixes")
    discover.add_argument("--json", action="store_true", help="Output JSON")
    discover.set_defaults(func=command_discover)

    claim = sub.add_parser("claim", help="Claim one Agent issue and checkout local branch")
    claim.add_argument("--issue", required=True, help="Issue reference e.g. owner/repo#123")
    claim.add_argument("--repo", dest="repo", default=None, help="owner/repo when issue number is not qualified")
    claim.add_argument("--base-branch", dest="base_branch", default=None, help="Base branch for new agent branch")
    claim.add_argument("--json", action="store_true", help="Output JSON summary")
    claim.set_defaults(func=command_claim)

    finalize = sub.add_parser("finalize", help="Run checks, create/update PR, and post status labels/comments")
    finalize.add_argument("--issue", required=True, help="Issue reference e.g. owner/repo#123")
    finalize.add_argument("--repo", dest="repo", default=None, help="owner/repo when issue number is not qualified")
    finalize.add_argument("--branch", dest="branch", default=None, help="Branch that contains fixes")
    finalize.add_argument("--result", required=True, choices=sorted(PR_LABELS), help="Final result for status labeling")
    finalize.add_argument("--pr-title", default=None, help="Override PR title")
    finalize.add_argument("--base-branch", dest="base_branch", default=None, help="PR base branch")
    finalize.add_argument("--run-tests", action="store_true", help="Run pytest before finalize")
    finalize.add_argument("--pytest-timeout", type=int, default=600, help="Pytest timeout in seconds")
    finalize.add_argument("--force-result", action="store_true", help="Allow final result different from auto-evaluation")
    finalize.add_argument("--allow-low-confidence", action="store_true", help="Allow confidence < 100")
    finalize.add_argument("--close-issue", action="store_true", help="Close issue when result is approved")
    finalize.add_argument("--json", action="store_true", help="Output JSON summary")
    finalize.set_defaults(func=command_finalize)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return int(args.func(args))
    except ValueError as exc:
        raise ToolError(str(exc))
    except ToolError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

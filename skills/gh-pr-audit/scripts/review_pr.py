#!/usr/bin/env python3
"""
Perform a deterministic local audit on a GitHub PR and optional GitHub updates.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_APPROVED_LABEL = "pr-review/approved"
DEFAULT_CHANGES_LABEL = "pr-review/needs-changes"
DEFAULT_UNCERTAIN_LABEL = "pr-review/uncertain"
DEFAULT_APPROVED_LABEL_COLOR = "0e8a16"
DEFAULT_CHANGES_LABEL_COLOR = "d93f0b"
DEFAULT_UNCERTAIN_LABEL_COLOR = "8b949e"


SEVERITY_SCORE = {"high": 2, "medium": 1, "low": 0}

GENERIC_PATTERNS = [
    (
        "high",
        "suspicious_secret",
        re.compile(r"(?i)\b(secret|api[_-]?key|access[_-]?token|auth[_-]?token|password)\b"),
        "Potential credential-like token pattern in source text.",
    ),
    (
        "high",
        "hardcoded_aws_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "Hard-coded AWS access key-like token pattern.",
    ),
    (
        "high",
        "eval_exec",
        re.compile(r"\b(eval|exec)\s*\("),
        "Potentially dangerous runtime execution.",
    ),
    (
        "medium",
        "todo_fixme",
        re.compile(r"\b(TODO|FIXME|XXX|HACK)\b"),
        "TODO/FIXME marker remains in changed content.",
    ),
]

SUBPROCESS_SHELL_PATTERN = re.compile(r"\bsubprocess\.\w+\(.*shell\s*=\s*True", re.IGNORECASE)


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    file: str | None = None
    line: int | None = None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "detail": self.detail,
        }


def _run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    try:
        process = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {command[0]}") from exc
    return process


def _run_json_command(command: list[str], *, cwd: Path | None = None, timeout: int = 120) -> dict[str, Any]:
    result = _run_command(command, cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "command failed")
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"failed to parse JSON output: {exc}") from exc


def _ensure_gh_auth(repo_root: Path) -> None:
    result = _run_command(["gh", "auth", "status"], cwd=repo_root)
    if result.returncode != 0:
        raise RuntimeError("gh auth status failed. Run `gh auth login` first.")


def _resolve_repo_root(repo_path: Path) -> Path:
    result = _run_command(["git", "rev-parse", "--show-toplevel"], cwd=repo_path)
    if result.returncode != 0:
        raise RuntimeError("Not a git repository.")
    return Path(result.stdout.strip())


def _resolve_pr_number(repo_root: Path, pr_arg: str | None) -> int:
    if pr_arg:
        stripped = pr_arg.strip()
        if stripped.isdigit():
            return int(stripped)
        match = re.search(r"/pull/(\d+)", stripped)
        if match:
            return int(match.group(1))
        raise ValueError(f"Unrecognized PR value: {pr_arg!r}")

    payload = _run_json_command(["gh", "pr", "view", "--json", "number"], cwd=repo_root)
    return int(payload["number"])


def _repository_identity(repo_root: Path) -> tuple[str, str]:
    payload = _run_json_command(["gh", "repo", "view", "--json", "nameWithOwner"], cwd=repo_root)
    full = payload["nameWithOwner"]
    owner, name = full.split("/", 1)
    return owner, name


def _get_pr_meta(repo_root: Path, pr_number: int) -> dict[str, Any]:
    fields = [
        "number",
        "title",
        "state",
        "isDraft",
        "url",
        "body",
        "baseRefName",
        "baseRefOid",
        "headRefName",
        "headRefOid",
        "additions",
        "deletions",
    ]
    return _run_json_command(
        ["gh", "pr", "view", str(pr_number), "--json", ",".join(fields)],
        cwd=repo_root,
    )


def _fetch_pr_refs(repo_root: Path, pr_number: int, pr_meta: dict[str, Any]) -> tuple[str, str]:
    fetch_pr = _run_command(["git", "fetch", "origin", f"pull/{pr_number}/head"], cwd=repo_root)
    if fetch_pr.returncode != 0:
        raise RuntimeError(f"Cannot fetch PR head: {fetch_pr.stderr.strip() or fetch_pr.stdout.strip()}")
    head_sha = _run_command(["git", "rev-parse", "FETCH_HEAD"], cwd=repo_root).stdout.strip()

    base_ref = pr_meta["baseRefName"]
    fetch_base = _run_command(["git", "fetch", "origin", base_ref], cwd=repo_root)
    if fetch_base.returncode != 0:
        raise RuntimeError(f"Cannot fetch base branch {base_ref}: {fetch_base.stderr.strip() or fetch_base.stdout.strip()}")

    base_sha = pr_meta.get("baseRefOid") or _run_command(
        ["git", "rev-parse", f"origin/{base_ref}"], cwd=repo_root
    ).stdout.strip()
    if not base_sha:
        raise RuntimeError("Unable to resolve base SHA.")
    return base_sha, head_sha


def _make_worktree(repo_root: Path, head_sha: str) -> Path:
    worktree_dir = Path(tempfile.mkdtemp(prefix=f"gh-pr-audit-pr-{head_sha[:8]}-"))
    add = _run_command(
        ["git", "worktree", "add", "--detach", str(worktree_dir), head_sha],
        cwd=repo_root,
        timeout=300,
    )
    if add.returncode != 0:
        raise RuntimeError(f"Cannot create PR worktree: {add.stderr.strip() or add.stdout.strip()}")
    return worktree_dir


def _remove_worktree(repo_root: Path, worktree_dir: Path) -> None:
    _run_command(["git", "worktree", "remove", "--force", str(worktree_dir)], cwd=repo_root, timeout=120)
    _run_command(["git", "worktree", "prune"], cwd=repo_root, timeout=120)


def _changed_files(repo_root: Path, base_sha: str, head_sha: str) -> list[tuple[str, str]]:
    diff = _run_command(
        ["git", "diff", "--name-status", "--find-renames", "--find-copies", f"{base_sha}..{head_sha}"],
        cwd=repo_root,
        timeout=180,
    )
    if diff.returncode != 0:
        raise RuntimeError(f"Cannot compute diff: {diff.stderr.strip() or diff.stdout.strip()}")
    changed = []
    for line in filter(None, diff.stdout.splitlines()):
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            path = parts[2]
        elif len(parts) >= 2:
            path = parts[1]
        else:
            continue
        changed.append((status, path))
    return changed


def _match_filters(path: str, filters: list[str]) -> bool:
    if not filters:
        return True
    normalized = path.replace("\\", "/")
    for item in filters:
        needle = item.replace("\\", "/").rstrip("/")
        if normalized == needle or normalized.startswith(f"{needle}/"):
            return True
    return False


def _project_scope(path: str) -> str:
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if len(parts) >= 2 and parts[0] == "projects":
        return f"{parts[0]}/{parts[1]}"
    return "repo-root"


def _scan_file_text(path: Path, findings: list[Finding], max_bytes: int) -> list[str]:
    if path.stat().st_size > max_bytes:
        return ["skipped-large-file"]
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return ["unreadable-file"]

    lines = content.splitlines()
    for index, line in enumerate(lines, start=1):
        for severity, code, pattern, message in GENERIC_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        severity=severity,
                        code=code,
                        message=message,
                        file=str(path),
                        line=index,
                        detail=line.strip()[:200],
                    )
                )
        if SUBPROCESS_SHELL_PATTERN.search(line):
            findings.append(
                Finding(
                    severity="high",
                    code="subprocess_shell",
                    message="subprocess call with shell=True may allow command injection.",
                    file=str(path),
                    line=index,
                    detail=line.strip()[:200],
                )
            )
    return []


def _syntax_checks_for_file(path: Path, findings: list[Finding], project_root: Path) -> tuple[bool, bool]:
    suffix = path.suffix.lower()
    passed = True
    executed = False
    if suffix in {".py", ".pyi"}:
        executed = True
        compile_result = _run_command(
            [sys.executable, "-m", "compileall", "-q", str(path)],
            cwd=project_root,
            timeout=60,
        )
        if compile_result.returncode != 0:
            findings.append(
                Finding(
                    severity="high",
                    code="python_syntax",
                    message="Python syntax check failed.",
                    file=str(path),
                    detail=(compile_result.stderr.strip() or compile_result.stdout.strip())[:200],
                )
            )
            passed = False
    elif suffix in {".sh", ".bash", ".zsh"}:
        executed = True
        shell_result = _run_command(["bash", "-n", str(path)], cwd=project_root, timeout=60)
        if shell_result.returncode != 0:
            findings.append(
                Finding(
                    severity="high",
                    code="shell_syntax",
                    message="Shell syntax check failed.",
                    file=str(path),
                    detail=(shell_result.stderr.strip() or shell_result.stdout.strip())[:200],
                )
            )
            passed = False
    elif suffix == ".json":
        executed = True
        try:
            with path.open("r", encoding="utf-8") as handle:
                json.load(handle)
        except Exception as exc:
            findings.append(
                Finding(
                    severity="medium",
                    code="json_invalid",
                    message="Invalid JSON syntax.",
                    file=str(path),
                    detail=str(exc)[:200],
                )
            )
            passed = False
    return passed, executed


def _has_pytest_module() -> bool:
    result = _run_command([sys.executable, "-m", "pytest", "--version"], timeout=30)
    return result.returncode == 0


def _run_local_tests(
    repo_root: Path,
    project_roots: set[str],
    *,
    run_tests: bool,
    timeout: int,
) -> list[Finding]:
    findings: list[Finding] = []
    if not run_tests:
        return findings

    for project in sorted(project_roots):
        project_path = repo_root if project == "repo-root" else repo_root / project
        if not project_path.exists():
            continue
        has_python = any(
            (project_path / marker).exists() for marker in ("pyproject.toml", "requirements.txt", "requirements.in")
        )
        has_tests = (project_path / "tests").is_dir()
        if not has_tests:
            findings.append(
                Finding(
                    severity="low",
                    code="tests_skipped",
                    message=f"Skipping automatic tests for `{project}`: missing tests directory.",
                    file=None,
                    detail="No `tests/` directory was found.",
                )
            )
            continue

        if not has_python and not (project_path / "requirements.txt").exists():
            findings.append(
                Finding(
                    severity="low",
                    code="tests_skipped",
                    message=f"Skipping automatic tests for `{project}`: missing pytest project markers.",
                    file=None,
                    detail="No pyproject.toml or requirements.txt found.",
                )
            )
            continue

        if not _has_pytest_module():
            findings.append(
                Finding(
                    severity="medium",
                    code="tests_tooling_missing",
                    message=f"Cannot run tests for `{project}`: pytest/python not available.",
                    file=None,
                    detail="Install pytest or ensure Python is on PATH.",
                )
            )
            continue

        command = [sys.executable, "-m", "pytest", "-q"]
        result = _run_command(command, cwd=project_path, timeout=timeout)
        if result.returncode != 0:
            findings.append(
                Finding(
                    severity="high",
                    code="tests_failed",
                    message=f"Pytest failed in `{project}`.",
                    file=None,
                    detail=(result.stderr.strip() or result.stdout.strip())[:800],
                )
            )
    return findings


def _pr_checks(pr_number: int, repo_root: Path, owner: str, repo: str) -> tuple[list[dict[str, Any]], bool]:
    checks_failed: list[dict[str, Any]] = []
    check_output = None

    fields = "name,state,conclusion,detailsUrl"
    try:
        check_output = _run_json_command(
            ["gh", "pr", "checks", str(pr_number), "--json", fields],
            cwd=repo_root,
        )
    except RuntimeError:
        # Fallback to broader fields for older gh versions.
        check_output = _run_json_command(
            ["gh", "pr", "checks", str(pr_number), "--json", "name,state,bucket,link,workflow"],
            cwd=repo_root,
        )

    if not isinstance(check_output, list):
        return checks_failed, True
    for check in check_output:
        state = str(check.get("state", "")).lower()
        conclusion = str(check.get("conclusion", "")).lower()
        bucket = str(check.get("bucket", "")).lower()
        details = check.get("detailsUrl") or check.get("link", "")
        failing = state in {"failure", "error", "timed_out", "action_required", "failed"} or conclusion in {
            "failure",
            "timed_out",
            "action_required",
            "cancelled",
            "error",
            "failed",
        } or bucket == "fail"

        if failing:
            checks_failed.append(
                {
                    "name": check.get("name", ""),
                    "state": state,
                    "conclusion": conclusion,
                    "detailsUrl": details,
                }
            )
    return checks_failed, any(item["state"] not in {"completed", "success", "passed"} for item in check_output)


def _ensure_label(owner: str, repo: str, label: str, color: str, description: str) -> None:
    create = _run_command(
        ["gh", "label", "create", label, "--color", color, "--description", description, "--repo", f"{owner}/{repo}"],
        timeout=120,
    )
    if create.returncode == 0:
        return
    stderr = (create.stderr or "").lower()
    stdout = (create.stdout or "").lower()
    if "already exists" in stderr or "already exists" in stdout:
        return
    raise RuntimeError(f"Cannot ensure label {label}: {create.stderr.strip() or create.stdout.strip()}")


def _remove_audit_labels(owner: str, repo: str, pr_number: int) -> None:
    for label in (DEFAULT_APPROVED_LABEL, DEFAULT_CHANGES_LABEL, DEFAULT_UNCERTAIN_LABEL):
        _run_command(
            [
                "gh",
                "pr",
                "edit",
                str(pr_number),
                "--remove-label",
                label,
                "--repo",
                f"{owner}/{repo}",
            ],
            timeout=60,
        )


def _apply_verdict_label(
    owner: str,
    repo: str,
    pr_number: int,
    verdict: str,
) -> str:
    label, color, description = (
        (DEFAULT_APPROVED_LABEL, DEFAULT_APPROVED_LABEL_COLOR, "Automated PR audit produced an Approved result")
        if verdict == "approved"
        else (
            DEFAULT_CHANGES_LABEL,
            DEFAULT_CHANGES_LABEL_COLOR,
            "Automated PR audit found blocking issues",
        )
        if verdict == "needs-changes"
        else (
            DEFAULT_UNCERTAIN_LABEL,
            DEFAULT_UNCERTAIN_LABEL_COLOR,
            "Automated PR audit could not determine status with full certainty",
        )
    )

    _ensure_label(owner, repo, label, color, description)
    _remove_audit_labels(owner, repo, pr_number)
    add = _run_command(
        [
            "gh",
            "pr",
            "edit",
            str(pr_number),
            "--add-label",
            label,
            "--repo",
            f"{owner}/{repo}",
        ],
        timeout=120,
    )
    if add.returncode != 0:
        raise RuntimeError(f"Cannot add label {label}: {add.stderr.strip() or add.stdout.strip()}")
    return label


def _post_comment(owner: str, repo: str, pr_number: int, body: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=True) as handle:
        handle.write(body)
        handle.flush()
        comment = _run_command(
            ["gh", "pr", "comment", str(pr_number), "--repo", f"{owner}/{repo}", "--body-file", handle.name],
            timeout=120,
        )
    if comment.returncode != 0:
        raise RuntimeError(f"Cannot post comment: {comment.stderr.strip() or comment.stdout.strip()}")


def _fmt_summary(
    verdict: str,
    confidence: int,
    pr_number: int,
    pr_url: str,
    findings: list[Finding],
    ci_failed: list[dict[str, Any]],
    test_findings: list[Finding],
    changed_count: int,
    project_scope: set[str],
) -> str:
    lines = [
        "<!-- gh-pr-audit -->",
        f"## GitHub PR Audit Verdict: {verdict.upper()}",
        f"- PR: [#{pr_number}]({pr_url})",
        f"- Confidence: `{confidence}%`",
        f"- Files reviewed: `{changed_count}`",
        f"- Project scope: `{', '.join(sorted(project_scope)) or 'repo-root'}`",
    ]
    if ci_failed:
        lines.append("")
        lines.append("### Failing checks")
        for item in ci_failed:
            url = item.get("detailsUrl") or ""
            target = f" - [{item.get('name', 'check')}]({url})" if url else f" - {item.get('name', 'check')}"
            lines.append(target)

    blocking_findings = [f for f in findings if f.severity == "high"]
    medium_findings = [f for f in findings if f.severity == "medium"]

    if blocking_findings:
        lines.append("")
        lines.append("### Blocking findings")
        for item in blocking_findings:
            location = f"{item.file}:{item.line}" if item.file and item.line else (item.file or "N/A")
            lines.append(f"- **{item.code}** ({location}) — {item.message}")
            if item.detail:
                lines.append(f"  - `{item.detail}`")

    if medium_findings:
        lines.append("")
        lines.append("### Additional findings")
        for item in medium_findings:
            location = f"{item.file}:{item.line}" if item.file and item.line else (item.file or "N/A")
            lines.append(f"- **{item.code}** ({location}) — {item.message}")

    if test_findings:
        lines.append("")
        lines.append("### Test findings")
        for item in test_findings:
            lines.append(f"- **{item.code}** — {item.message}")
            if item.detail:
                lines.append(f"  - `{item.detail[:700]}`")

    if not findings and not ci_failed and not test_findings:
        lines.append("")
        lines.append("No blocking findings detected.")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit GitHub PRs with local checkout, review, and PR labeling/commenting."
    )
    parser.add_argument("--repo", default=".", help="Path within the target repository.")
    parser.add_argument("--pr", default=None, help="PR number or URL. Defaults to current branch PR.")
    parser.add_argument(
        "--project-filter",
        action="append",
        default=[],
        help="Only include files under specific paths like projects/<slug>.",
    )
    parser.add_argument("--run-tests", action="store_true", help="Run local pytest for affected projects.")
    parser.add_argument(
        "--pytest-timeout",
        type=int,
        default=600,
        help="Per-project pytest timeout in seconds.",
    )
    parser.add_argument("--post", action="store_true", help="Post comment and apply label on the PR.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output for downstream automation.")
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=1_000_000,
        help="Skip text pattern scanning for files larger than this number of bytes.",
    )
    args = parser.parse_args()

    repo_root = _resolve_repo_root(Path(args.repo))
    _ensure_gh_auth(repo_root)
    pr_number = _resolve_pr_number(repo_root, args.pr)

    pr_meta = _get_pr_meta(repo_root, pr_number)
    owner, repo = _repository_identity(repo_root)
    pr_url = pr_meta.get("url", "")

    base_sha, head_sha = _fetch_pr_refs(repo_root, pr_number, pr_meta)
    changed = _changed_files(repo_root, base_sha, head_sha)
    if args.project_filter:
        filtered = [(status, path) for status, path in changed if _match_filters(path, args.project_filter)]
    else:
        filtered = changed

    worktree_dir: Path | None = None
    try:
        worktree_dir = _make_worktree(repo_root, head_sha)
        findings: list[Finding] = []
        tested_projects: set[str] = set()
        syntax_checks_ran = False
        for _status, path in filtered:
            project_scope = _project_scope(path)
            tested_projects.add(project_scope)
            file_path = worktree_dir / path
            if file_path.exists() and file_path.is_file():
                issues = _scan_file_text(file_path, findings, args.max_file_bytes)
                for marker in issues:
                    if marker == "skipped-large-file":
                        findings.append(
                            Finding(
                                severity="low",
                                code="large_file",
                                message="Skipped detailed text scan due size limit.",
                                file=str(file_path),
                                detail="Large file omitted from heuristic scan.",
                            )
                        )
                    elif marker == "unreadable-file":
                        findings.append(
                            Finding(
                                severity="low",
                                code="unreadable_file",
                                message="Could not read file text for heuristic checks.",
                                file=str(file_path),
                            )
                        )
                syntax_passed, syntax_executed = _syntax_checks_for_file(file_path, findings, worktree_dir)
                syntax_checks_ran = syntax_checks_ran or syntax_executed
                if not syntax_passed:
                    pass

        ci_failed, ci_incomplete = _pr_checks(pr_number, repo_root, owner, repo)
        test_findings = _run_local_tests(
            repo_root,
            tested_projects,
            run_tests=args.run_tests,
            timeout=args.pytest_timeout,
        )

        high_count = len([item for item in findings if item.severity == "high"])
        medium_count = len([item for item in findings if item.severity == "medium"])
        low_count = len([item for item in findings if item.severity == "low"])
        blocking = bool(ci_failed) or any(item.code in {"tests_failed", "python_syntax", "shell_syntax"} for item in findings)
        low_confidence_penalties = 0

        if not syntax_checks_ran:
            low_confidence_penalties += 20
        if ci_incomplete:
            low_confidence_penalties += 15
        if args.run_tests and any(item.code == "tests_skipped" for item in test_findings):
            low_confidence_penalties += 10

        confidence = max(0, 100 - low_confidence_penalties)

        if blocking or ci_failed or any(item.severity == "high" for item in findings):
            verdict = "needs-changes"
        elif confidence == 100 and not low_count and not medium_count:
            verdict = "approved"
        else:
            verdict = "uncertain"

        project_scope = {_project_scope(path) for _status, path in filtered}

        if args.post:
            applied_label = _apply_verdict_label(owner, repo, pr_number, verdict)
            comment_body = _fmt_summary(
                verdict,
                confidence,
                pr_number,
                pr_url,
                findings,
                ci_failed,
                test_findings,
                len(filtered),
                project_scope,
            )
            _post_comment(owner, repo, pr_number, comment_body)
        else:
            applied_label = None

        if args.json:
            payload: dict[str, Any] = {
                "pr": {
                    "number": pr_number,
                    "url": pr_url,
                    "title": pr_meta.get("title", ""),
                    "state": pr_meta.get("state", ""),
                    "is_draft": bool(pr_meta.get("isDraft", False)),
                },
                "status": verdict,
                "confidence_percent": confidence,
                "projects": sorted(project_scope),
                "changed_files": len(filtered),
                "findings": [item.as_dict() for item in findings],
                "tests": [item.as_dict() for item in test_findings],
                "ci": {"failing_checks": ci_failed, "incomplete": ci_incomplete},
                "post": {"enabled": args.post, "label": applied_label},
            }
            print(json.dumps(payload, indent=2))
        else:
            summary = _fmt_summary(
                verdict,
                confidence,
                pr_number,
                pr_url,
                findings,
                ci_failed,
                test_findings,
                len(filtered),
                project_scope,
            )
            print(summary)

        if verdict == "needs-changes":
            return 2
        if verdict == "uncertain":
            return 1
        return 0

    finally:
        if worktree_dir is not None:
            _remove_worktree(repo_root, worktree_dir)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

#!/usr/bin/env bash
set -euo pipefail

remote="origin"
branch=""
use_current=0

usage() {
  cat <<'EOF'
Usage:
  sync-repo.sh [--branch <name>] [--current]

Options:
  --branch <name>  Sync the named branch from origin/<name>.
  --current        Sync the currently checked out branch.

Default behavior:
  Sync the remote default branch from origin/HEAD.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      if [[ $# -lt 2 ]]; then
        echo "[ERROR] --branch requires a branch name." >&2
        exit 1
      fi
      branch="$2"
      shift 2
      ;;
    --current)
      use_current=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -n "$branch" && $use_current -eq 1 ]]; then
  echo "[ERROR] Use either --branch or --current, not both." >&2
  exit 1
fi

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "[ERROR] Not inside a git repository." >&2
  exit 1
}

git remote get-url "$remote" >/dev/null 2>&1 || {
  echo "[ERROR] Remote '$remote' does not exist." >&2
  exit 1
}

current_branch="$(git branch --show-current)"
worktree_dirty=0
if [[ -n "$(git status --porcelain)" ]]; then
  worktree_dirty=1
fi

git fetch --prune "$remote"

if [[ $use_current -eq 1 ]]; then
  if [[ -z "$current_branch" ]]; then
    echo "[ERROR] Detached HEAD cannot be used with --current." >&2
    exit 1
  fi
  target_branch="$current_branch"
elif [[ -n "$branch" ]]; then
  target_branch="$branch"
else
  remote_head="$(git symbolic-ref --quiet --short "refs/remotes/$remote/HEAD" 2>/dev/null || true)"
  if [[ -z "$remote_head" ]]; then
    echo "[ERROR] Could not resolve $remote/HEAD. Re-run with --branch <name>." >&2
    exit 1
  fi
  target_branch="${remote_head#"$remote/"}"
fi

git show-ref --verify --quiet "refs/remotes/$remote/$target_branch" || {
  echo "[ERROR] Remote branch '$remote/$target_branch' does not exist." >&2
  exit 1
}

if [[ "$current_branch" != "$target_branch" && $worktree_dirty -eq 1 ]]; then
  echo "[ERROR] Worktree has uncommitted changes. Refusing to switch from '$current_branch' to '$target_branch'." >&2
  echo "        Commit, stash, or discard changes explicitly before syncing another branch." >&2
  exit 1
fi

if git show-ref --verify --quiet "refs/heads/$target_branch"; then
  if [[ "$current_branch" != "$target_branch" ]]; then
    git switch "$target_branch"
  fi
else
  git switch -c "$target_branch" --track "$remote/$target_branch"
fi

git pull --ff-only "$remote" "$target_branch"

echo "[OK] Synced '$target_branch' with '$remote/$target_branch'."
git status -sb

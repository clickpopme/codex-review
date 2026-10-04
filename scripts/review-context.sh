#!/usr/bin/env bash
# Read-only context probe for the codex-review skill.
# Usage: bash review-context.sh [repository-directory]
# Prints one JSON object describing the Git repository that contains the
# given directory (default: current directory). Never modifies anything.
set -eu

# Derive an "owner/repo" style display slug from a remote URL. Falls back to
# the directory name for local or unusual remotes.
repo_slug() {
  local remote=$1 fallback=$2 path
  case "$remote" in
    file://*) printf '%s\n' "$fallback"; return ;;
    *://*) path=${remote#*://}; path=${path#*/} ;;
    *@*:*|[!/:]*:*) path=${remote#*:} ;;
    *) printf '%s\n' "$fallback"; return ;;
  esac
  path=${path#/}
  path=${path#"~"}
  path=${path%/}
  path=${path%.git}
  case "$path" in
    */*) printf '%s\n' "$path" ;;
    *) printf '%s\n' "$fallback" ;;
  esac
}

review_context() {
  local root remote slug sha branch candidate ahead scope key status
  root=$(git -C "${1:-.}" rev-parse --show-toplevel) || return 1
  if remote=$(git -C "$root" remote get-url origin 2>/dev/null); then
    slug=$(repo_slug "$remote" "${root##*/}")
  else
    slug=${root##*/}
  fi
  sha=$(git -C "$root" rev-parse --verify HEAD 2>/dev/null) || {
    printf '%s\n' 'No HEAD commit; establish a review baseline first.' >&2
    return 1
  }
  branch=$(git -C "$root" symbolic-ref --short -q HEAD) || branch=HEAD

  # Candidate base branch for a clean-tree review: the remote default branch
  # when known and valid, otherwise the first of the usual names that exists.
  candidate=$(git -C "$root" symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null) || candidate=''
  if [ -z "$candidate" ] || ! git -C "$root" rev-parse --verify "$candidate^{commit}" >/dev/null 2>&1; then
    candidate=''
    for remote in origin/main origin/master main master; do
      if git -C "$root" rev-parse --verify "$remote^{commit}" >/dev/null 2>&1; then
        candidate=$remote
        break
      fi
    done
  fi
  # A base that HEAD is not ahead of (for example the branch we are on) would
  # produce an empty review, so it is not offered.
  ahead=0
  if [ -n "$candidate" ]; then
    ahead=$(git -C "$root" rev-list --count "$candidate..HEAD")
    [ "$ahead" -gt 0 ] || candidate=''
  fi

  # Any uncommitted change selects the uncommitted scope; no file-count or
  # file-type heuristics.
  status=$(git -C "$root" status --porcelain --untracked-files=all) || return 1
  if [ -n "$status" ]; then
    scope=uncommitted
  else
    scope=ask
  fi
  key=$(printf '%s' "$root" | git hash-object --stdin)
  jq -n --arg root "$root" --arg repo "$slug" --arg repo_key "$key" \
    --arg sha "$sha" --arg branch "$branch" --arg scope "$scope" \
    --arg base "$candidate" --argjson ahead "$ahead" \
    '{root:$root,repo:$repo,repo_key:$repo_key,commit_sha:$sha,branch:$branch,
      default_scope:$scope,candidate_base:$base,commits_ahead_of_base:$ahead}'
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  review_context "${1:-.}"
fi

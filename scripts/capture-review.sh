#!/usr/bin/env bash
# Run one Codex review and capture everything it produces into a private,
# unique run directory. Does not parse findings, modify source, write config,
# or create tickets.
#
# Usage: bash capture-review.sh ROOT MODE VALUE [PENDING_DIR]
#   ROOT        absolute Git root pinned in Phase 0
#   MODE/VALUE  uncommitted ''            staged, unstaged and untracked changes
#               base <ref>               merge-base of HEAD and <ref> -> working tree
#               commit <sha>             one commit's changes
#               prompt /abs/prompt.txt   custom instructions only (no scope flag)
#   PENDING_DIR absolute directory for run folders (default ~/.codex-reviews/pending)
#
# The run directory path is printed on stdout BEFORE Codex starts, so an
# interrupted run can still be found. On completion it contains:
#   context.json codex-version.txt final.txt stdout.txt stderr.txt status.json
# Exit status is Codex's exit status (0 on success).
set -eu
umask 077
root=${1:?Pass the pinned Git root}
mode=${2:?Pass uncommitted, base, commit, or prompt}
value=${3-}
pending=${4:-${HOME:?set HOME or pass an absolute PENDING_DIR as the 4th argument}/.codex-reviews/pending}

actual=$(git -C "$root" rev-parse --show-toplevel)
[ "$actual" = "$root" ] || { printf '%s\n' 'ROOT must be the pinned absolute Git root.' >&2; exit 1; }
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
context=$(bash "$script_dir/review-context.sh" "$root")

# Optional repository config: only review.model is read here.
config=$root/.codex-review.json
model=${CODEX_REVIEW_MODEL-}
if [ -e "$config" ] || [ -L "$config" ]; then
  [ ! -L "$config" ] || { printf '%s\n' 'Refusing to read .codex-review.json through a symlink.' >&2; exit 1; }
  jq -e 'type == "object" and ((.review.model | type) == "string" or (.review.model | type) == "null")' "$config" >/dev/null \
    || { printf 'Invalid %s: must be a JSON object and review.model must be a string or null.\n' "$config" >&2; exit 1; }
  [ -n "$model" ] || model=$(jq -r '.review.model // empty' "$config")
fi

# Version and capability gate. 0.153.4 is the tested floor.
version=$(codex --version)
number=$(printf '%s\n' "$version" | sed -nE 's/^codex-cli ([0-9]+\.[0-9]+\.[0-9]+).*$/\1/p' | head -n 1)
if [ -z "$number" ]; then
  printf 'Could not parse "codex --version" output (%s); expected "codex-cli X.Y.Z". Check the installation manually.\n' "$version" >&2
  exit 1
fi
if ! printf '%s\n' "$number" | awk -F. 'NF == 3 && ($1 > 0 || $2 > 153 || ($2 == 153 && $3 >= 4)) {ok=1} END {exit !ok}'; then
  printf 'This skill requires Codex CLI >= 0.153.4 (found %s); upgrade or choose another reviewer.\n' "$number" >&2
  exit 1
fi
help=$(codex exec review --help)
for flag in --config --uncommitted --base --commit --output-last-message --ephemeral; do
  case "$help" in *"$flag"*) ;; *) printf 'Codex is missing a required "exec review" flag: %s\n' "$flag" >&2; exit 1 ;; esac
done

# Read-only sandbox for any commands the reviewer runs; no session files kept
# by Codex; final message captured to a file.
args=(-c 'sandbox_mode="read-only"' --ephemeral)
if [ -n "$model" ]; then
  case "$model" in *[!a-zA-Z0-9._:/-]*) printf '%s\n' 'Unsupported characters in model identifier.' >&2; exit 1 ;; esac
  # The review thread uses review_model when set, otherwise the session model.
  args+=(-c "model=\"$model\"" -c "review_model=\"$model\"")
fi
case "$mode" in
  uncommitted)
    [ -z "$value" ] || { printf '%s\n' 'VALUE must be empty for uncommitted mode.' >&2; exit 2; }
    args+=(--uncommitted) ;;
  base)
    # Verify the ref exists, but pass the user's name so Codex applies its own
    # base-branch logic (merge-base of HEAD and the ref, compared to the working tree).
    git -C "$root" rev-parse --verify --end-of-options "$value^{commit}" >/dev/null
    args+=(--base "$value") ;;
  commit)
    resolved=$(git -C "$root" rev-parse --verify --end-of-options "$value^{commit}")
    args+=(--commit "$resolved") ;;
  prompt)
    case "$value" in /*) ;; *) printf '%s\n' 'Prompt path must be absolute.' >&2; exit 2 ;; esac
    [ -f "$value" ] || { printf '%s\n' 'Prompt file missing.' >&2; exit 2; } ;;
  *) printf '%s\n' 'Unsupported scope mode (use uncommitted, base, commit, or prompt).' >&2; exit 2 ;;
esac

case "$pending" in /*) ;; *) printf '%s\n' 'PENDING_DIR must be absolute.' >&2; exit 2 ;; esac
case "$pending" in
  */|*/.|*/..|*/./*|*/../*) printf '%s\n' 'PENDING_DIR must be normalized (no trailing slash, "." or ".." components).' >&2; exit 2 ;;
esac
check=$pending
while [ "$check" != / ]; do
  [ ! -L "$check" ] || { printf 'Refusing a symlink in the artifact path: %s\n' "$check" >&2; exit 1; }
  check=$(dirname -- "$check")
done
mkdir -p "$pending"
run=$(mktemp -d "$pending/run.XXXXXXXX")
printf '%s\n' "$run"
printf '%s\n' "$context" > "$run/context.json"
printf '%s\n' "$version" > "$run/codex-version.txt"
started=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

status=0
if [ "$mode" = prompt ]; then
  (cd -- "$root" && codex exec review "${args[@]}" -o "$run/final.txt" - < "$value") > "$run/stdout.txt" 2> "$run/stderr.txt" || status=$?
else
  (cd -- "$root" && codex exec review "${args[@]}" -o "$run/final.txt") > "$run/stdout.txt" 2> "$run/stderr.txt" || status=$?
fi
if [ "$status" -eq 0 ] && [ ! -s "$run/final.txt" ]; then
  printf '%s\n' 'Codex exited 0 but wrote no final message; treating the run as failed.' >&2
  status=1
fi
if [ "$status" -eq 0 ] && grep -Fxq 'Reviewer failed to output a response.' "$run/final.txt"; then
  printf '%s\n' 'Codex reported that the reviewer produced no response; treating the run as failed.' >&2
  status=1
fi
chmod 600 "$run"/* 2>/dev/null || true
jq -n --argjson exit_code "$status" --arg mode "$mode" --arg value "$value" \
  --arg model "$model" --arg started "$started" \
  '{exit_code:$exit_code,scope:{mode:$mode,value:$value},model:$model,started_at:$started,final:"final.txt"}' > "$run/status.json"
exit "$status"

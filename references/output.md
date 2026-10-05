# Output, parsing and local records

## The run directory

`capture-review.sh` prints its run directory (`~/.codex-reviews/pending/run.XXXXXXXX`
by default) before Codex starts. Use exactly that path; never "the newest"
directory. On completion it contains:

| File | Contents |
| --- | --- |
| `context.json` | output of review-context.sh at run time |
| `codex-version.txt` | `codex --version` |
| `final.txt` | Codex's final message — the review itself |
| `stdout.txt` | rendered review again, with a trailing newline (0.153.4) |
| `stderr.txt` | model/session banner, progress, command output, diagnostics, and the review again |
| `status.json` | `exit_code`, `scope`, `model`, `started_at`, `final` |

A run is complete only when `exit_code` is 0 and `final.txt` is non-empty
and does not contain the exact failure line described below.
Anything else — non-zero exit, interruption (no `status.json`), auth or model
errors in `stderr.txt` — is a failed run: say so, keep the files, do not
propose fixes or tickets. Informational lines on stderr with exit 0 are not a
failure.

## Format of final.txt (Codex 0.153.4)

Live fixture reviews on 0.153.4 produced the following structure (including
prompt mode). Text and priorities are model-generated, not fixed wording.
`final.txt` had no trailing newline; stdout repeated it with one added.
Codex renders its structured review as plain text:

```text
<overall explanation, one to three sentences, optional>

Full review comments:          (or "Review comment:" for a single finding)

- [P1] Imperative title under 80 chars — /absolute/path/to/file.ext:12-14
  One-paragraph body explaining why this is a problem, citing files, lines
  or functions.

- [P3] Another title — /absolute/path/to/other.ext:40-40
  Body.
```

Rules:

- The priority is the `[Pn]` tag at the start of the title; strip it from the
  title. Mapping: P0 and P1 → High (keep "P0" in the record), P2 → Medium,
  P3 → Low, Nit/Note → Nit, missing → Unspecified (still manual, never silently
  skipped).
- The location is the text after the em dash: `path:start-end`. Paths are
  absolute. Convert to a `REPO_ROOT`-relative path only if the absolute path
  resolves inside `REPO_ROOT` (and is not a symlink escaping it); otherwise set
  the path to null and keep the finding manual.
- Body lines are indented two spaces; keep the whole body.
- No `Full review comments:`/`Review comment:` block and an explanation such as
  "patch is correct" means a clean review with no findings. On a clean tree,
  `--uncommitted` returned exit 0 and only: "The working tree is clean: there
  are no staged, unstaged, or untracked changes to review." This confirms an
  empty scope, not the correctness of already committed code.
- The exact line `Reviewer failed to output a response.` means the review
  failed even though the exit code was 0.
- Open each cited location and check that the finding describes the current
  code before using it. Record a `fix_confidence` of `explicit` (a `Fix:` line
  with a concrete change), `described` (the body states a concrete remedy), or
  `none`. Confidence is about how clear the remedy is, not whether it is safe;
  Phase 5 decides that.
- Deduplicate on the full tuple (path, line range, priority, title, body).
  Keep distinct findings that share a title.

Other reviewers are normalized into the same shape by you, with
`REPO_ROOT`-relative paths.

## findings.txt and review.json (schema v1)

Write the normalized findings to `RUN_DIR/findings.txt` with the Write tool,
one section per file:

```text
Checking src/example.ts...
- **High:** Failure title (lines 42-44). Original priority: P1.
  Body as written by the reviewer.
  Fix: Concrete remedy, if the reviewer gave one.
  Fix confidence: explicit|described|none.
```

Then, in one Bash call with `RUN_DIR` set to the run directory:

```bash
RUN_DIR=/absolute/path/to/run.XXXXXXXX
(
  set -eu
  umask 077
  jq -e '.exit_code == 0' "$RUN_DIR/status.json" >/dev/null
  tmp=$(mktemp "$RUN_DIR/review.XXXXXXXX")
  trap 'rm -f "$tmp"' EXIT
  jq -n --slurpfile context "$RUN_DIR/context.json" \
    --slurpfile status "$RUN_DIR/status.json" \
    --rawfile raw "$RUN_DIR/findings.txt" \
    '{schema_version:"1",repo:$context[0].repo,
      reviewed_at:$status[0].started_at,commit_sha:$context[0].commit_sha,
      branch:$context[0].branch,raw_output:$raw,
      repo_key:$context[0].repo_key,scope:$status[0].scope}' > "$tmp"
  mv "$tmp" "$RUN_DIR/review.json"
)
```

`review.json` has six required string fields (`schema_version` "1", `repo`,
`reviewed_at`, `commit_sha`, `branch`, `raw_output`) plus `repo_key` and
`scope`. `--rawfile` is used for the findings text so that size, quoting and
trailing newlines never matter. Never splice reviewer text into a shell
command or a jq program.

## Fix backups (Phase 6/7)

For each fix candidate `N`, before the preview, in one Bash call:

```bash
RUN_DIR=/absolute/path/to/run.XXXXXXXX
REPO_ROOT=/absolute/path/to/repo
REL_PATH=src/example.ts
N=1
(
  set -eu
  umask 077
  mkdir -p "$RUN_DIR/backups/$N"
  printf '%s\n' "$REL_PATH" > "$RUN_DIR/backups/$N/path.txt"
  cp -p "$REPO_ROOT/$REL_PATH" "$RUN_DIR/backups/$N/original"
  git -C "$REPO_ROOT" status --porcelain -- "$REL_PATH" > "$RUN_DIR/backups/$N/status.txt"
  chmod 600 "$RUN_DIR/backups/$N"/*
)
```

Immediately before editing, confirm nothing changed:
`cmp -s "$RUN_DIR/backups/$N/original" "$REPO_ROOT/$REL_PATH"` (exit 0) and the
same `git status --porcelain` line. Make the edit with the Edit tool and note
the exact old/new strings in your reasoning. To roll back, apply the inverse
Edit (new → old) and then `cmp` the file against `original`; if they differ,
stop and tell the user both versions exist (never overwrite the file with the
backup while other changes may be present). Keep backups until the user has
accepted the result. Files written with the Write tool are created with the
user's umask, so `chmod 600` anything you add to the run directory.

## outcomes.json (Phase 9)

Written beside `review.json`, with the Write tool:

```json
{
  "schema_version": "1",
  "findings": [
    {
      "path": "src/example.ts",
      "line": 42,
      "severity": "Low",
      "title": "Remove unused variable",
      "state": "applied",
      "reason": "",
      "checks": ["npm test (pass)"],
      "ticket_url": null
    }
  ]
}
```

`state` is one of `applied`, `reverted`, `manual`, `skipped`, `awaiting-approval`
(unattended runs that stopped at Phase 6; `plan.md` holds the preview).

## Privacy and retention

Run directories can contain source code, paths, secrets that tools printed, and
review text. The helper creates them with mode 0700/0600 and refuses symlinked
locations. Do not commit them, upload them, or paste raw transcripts into
tickets. Deleting a run directory removes only this skill's records; Codex
keeps its own logs under `~/.codex` (the helper passes `--ephemeral` so no
session file is written for the review itself). Uninstalling the skill deletes
nothing under `~/.codex-reviews`.

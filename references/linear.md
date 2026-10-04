# Optional Linear tickets

Review works without Linear. Phase 8 runs only when `skip_linear` is `false`,
the user has not asked for "no tickets", and Linear tools are connected to the
session. Nothing here assumes a particular MCP server name: look at the
available tools' names, descriptions and input schemas for ones that list
teams, projects, labels and users, search issues, and create an issue. If no
usable set exists, say so and leave manual findings in the run directory —
that is not a failed review.

## Before asking for approval (Phase 6)

- Resolve `linear.team_key` to a team ID in the connected workspace. Never pick
  the first team. Verify `linear.project_id` belongs to that team, resolve
  label names to IDs (ask before creating a missing label), and resolve the
  assignee if configured. Cache these for this run only.
- Show every ticket in full — title, body, team/project, labels, assignee —
  including any code excerpt that will be sent. Keep secrets and raw transcripts
  out. The body contains: file and line range, severity and original priority,
  reviewed commit and scope **mode** (never a prompt-file path, the repository
  root or any other local absolute path), the finding's evidence and impact,
  the remedy if known, and the fingerprint. Add a source link only when the
  remote host and path are verified and the cited content exists at that
  commit; uncommitted lines are not linkable. Title: up to 140 characters.

## Duplicates and state

Identity is the context's `repo_key` (hash of the pinned root), not the display
slug. Fingerprint = `git hash-object --stdin` over a deterministic JSON string
of `repo_key`, commit, scope, relative path, line, normalized title and body.
Before creating, check both `~/.codex-reviews/ticketed.json` and a Linear issue
search for the fingerprint. "Force re-ticket" still requires the user to
approve the duplicate explicitly.

`~/.codex-reviews/ticketed.json` is written only after a confirmed creation:

```json
{
  "<repo-key>": {
    "<fingerprint>": {
      "linear_issue_id": "<returned id>",
      "linear_issue_url": "<returned url>",
      "title": "Finding title",
      "ticketed_at": "<UTC timestamp>"
    }
  }
}
```

Update it in one Bash call: take a `mkdir` lock beside the file, re-read it,
merge, write a private temp file in the same directory, `mv` it into place,
release the lock. If the lock is held, stop and report rather than risk losing
updates. Do not hold the lock across a Linear call.

## Failures

If a create call times out or returns an ambiguous result, search Linear for
the fingerprint before retrying; if that cannot settle it, stop and report the
uncertainty. Read calls may retry rate limits up to three times with backoff.
If the issue was created but the local state write failed, report the returned
ID/URL and repair the state file without creating the issue again.

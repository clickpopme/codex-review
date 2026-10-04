# Changelog

## 1.0.0 — 2026-10-04

First public release.

- Runs `codex exec review` on uncommitted changes by default, or against a base
  branch or a single commit on request; captures Codex's final message with
  `-o`, runs it `--ephemeral` and in a read-only sandbox.
- Checks each finding against the current code, then proposes small
  single-file fixes for Medium-or-lower findings and leaves the rest for you.
- Every edit and every Linear ticket requires approval of a concrete plan shown
  first; no configuration value can grant it.
- Fixes are made one at a time with byte-exact backups under
  `~/.codex-reviews/`; the skill never stages, commits, stashes or resets.
- Configuration (`.codex-review.json`) is optional; nothing is written into the
  reviewed repository.
- Linear integration is optional and works with any connected Linear MCP tools.
- Installs as a plain personal or project skill, or as a Claude Code plugin.

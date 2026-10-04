# Troubleshooting

| Symptom | What to do |
| --- | --- |
| Skill not listed | The install must contain `SKILL.md`, `references/`, `scripts/` and `examples/`. Restart Claude Code. Plain install: `/codex-review`; plugin install: `/codex-review:codex-review`. |
| "Base directory for this skill" line missing | Update Claude Code; the skill needs it to locate its scripts. Do not guess a path. |
| Wrong repository | Re-run `review-context.sh` from the user's directory. Never take a repository from old run records. |
| `No HEAD commit` | The repository has no commits yet. Ask the user to make a first commit; do not make one. |
| `codex: command not found` / version too old | `npm install -g @openai/codex` (0.153.4 or newer), then `codex login`. |
| `Could not parse "codex --version"` | A newer Codex changed its version banner. Report the raw text; the user can check the installation manually. |
| `Codex is missing a required "exec review" flag` | The installed Codex predates `-o`/`--ephemeral` on `exec review`; upgrade. |
| Login failure | The user runs `codex login` (or `printenv OPENAI_API_KEY \| codex login --with-api-key`). Never ask for a key in chat. |
| Model not found | A pinned model (`CODEX_REVIEW_MODEL` or `review.model`) is unavailable. Offer to rerun with the CLI default; do not guess another name. |
| `cannot be used with '[PROMPT]'` | Scope flags and a prompt are exclusive. Use `prompt` mode without a scope flag, or a scope without a prompt. |
| Bash tool timed out during the review | The run was interrupted; the run directory printed earlier has no `status.json`. Treat it as failed and rerun with `run_in_background: true` or `timeout: 600000`. |
| `final.txt` empty or `Reviewer failed to output a response.` | Failed review even if exit was 0. Show `stderr.txt`; do not report "no findings". |
| `Refusing a symlink in the artifact path` | A component of the pending directory is a symlink (on macOS this includes `/tmp` and `$TMPDIR`). Use the default `~/.codex-reviews/pending` or pass another non-symlinked absolute directory. |
| `Invalid .codex-review.json` | The config is not a JSON object or `review.model` is not a string/null. Fix the file; config is optional, so deleting it also works. |
| Clean tree, no base offered | HEAD has no commits beyond the detected base (for example you are on `main`). Offer `commit HEAD` or ask for a branch to compare against. |
| Linear absent or disabled | Manual findings stay in the run directory; the review is still complete. |
| Linear create timed out | Search Linear for the fingerprint before retrying. |
| Required check unavailable | Leave the fix manual; never waive a required check silently. |
| Fix failed validation | Reverse only that edit and `cmp` against the backup. Never reset or restore from HEAD. |

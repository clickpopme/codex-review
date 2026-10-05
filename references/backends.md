# Reviewer backends

## Codex CLI (`codex-review`) — the default

Requires Codex CLI **0.153.4 or newer** (the version this package was built
and mock-tested against; live fixture checks also passed on 0.153.4). The capture helper checks `codex --version` and that
`codex exec review --help` lists the flags it needs; older or unparseable
versions stop with a message rather than guessing.

How the helper runs Codex (source-checked on 0.153.4; the four scope modes
and an explicit model pin were also exercised on live fixtures):

- `codex exec review` is the non-interactive review command. Scope flags
  `--uncommitted`, `--base <ref>` and `--commit <sha>` are mutually exclusive
  and none of them can be combined with a custom prompt (exit 2). A custom
  prompt is therefore its own mode (`prompt`), passed on stdin with `-`.
- `-o RUN_DIR/final.txt` makes Codex write its final message to a file, so the
  findings never have to be dug out of a transcript. In live 0.153.4 runs,
  stdout repeated this review with a trailing newline, and stderr included
  the model banner, command transcript and review. `--ephemeral` stops Codex
  keeping its own session file for the run. `-c 'sandbox_mode="read-only"'`
  keeps any commands the reviewer runs (such as `git diff`) read-only.
- A model is pinned only when `CODEX_REVIEW_MODEL` or `review.model` is set, via
  `-c model=… -c review_model=…` (the review thread prefers `review_model`).
  Otherwise Codex's own configured model is used. Identifiers may contain only
  letters, digits and `. _ : / -`.
- `--base <ref>` means: find the merge base of HEAD and `<ref>`, then review
  the difference from that commit to the **working tree** — so uncommitted
  changes are included. Use `commit` or a clean tree for committed-only review.
- Codex reads whatever it decides it needs for context, not just the diff, and
  it also applies the reviewed repository's own `.codex/` config and
  `AGENTS.md` if that repository is trusted in Codex. Mention this if the
  repository contains `.codex/` or `AGENTS.md`.

Scope wording → helper mode:

| User says | Mode |
| --- | --- |
| nothing / "my changes" / "uncommitted" | `uncommitted ''` |
| "against main", "the branch", "the PR" | `base main` (or the named ref) |
| "last commit", a SHA | `commit HEAD` / `commit <sha>` |
| "only staged", named files, a focus such as "security only" | `prompt /abs/file.txt` after agreeing the instruction text with the user; write the file with the Write tool |

Invocation (one Bash call, in the background or with a 10-minute timeout):

```bash
SKILL_DIR=/absolute/path/to/installed/codex-review   # from "Base directory for this skill"
REPO_ROOT=/absolute/path/to/repo                     # from review-context.sh
bash "$SKILL_DIR/scripts/capture-review.sh" "$REPO_ROOT" uncommitted ''
```

## Project script (`script`)

If `REPO_ROOT/scripts/ai-review.sh` exists, read the whole script and anything
it calls before considering it: it can run arbitrary commands and send data
anywhere. Use it only after the user has seen a summary of what it does and
approved running it; a committed `"preferred_backend": "script"` is a
preference, not that approval. Capture its stdout and stderr to files under a
run directory of your own, validate any JSON it produces, and treat its claims
about scope and repository as unverified.

## chatgpt wrapper (`chatgpt`)

An executable called `chatgpt` has no standard interface. Read its `--help`,
confirm the provider, model and stdin handling, and use it only as an approved
fallback. Review one file at a time from a NUL-delimited file list, honour
`review.skip_files_larger_than_kb`, write each response straight to a file,
and report partial coverage.

## GitHub Copilot (`gh-copilot`)

Probe `command -v copilot` and `gh extension list` (for `gh-copilot`), then
read the help for an actual review subcommand. Do not assume one exists or
invent flags. If neither executable exists, the adapter is unavailable.

## Claude subagent (`claude-subagent`)

Only when the user explicitly chooses it or nothing else is installed, and only
after saying that this uses the Claude runtime (not OpenAI) and ignores Codex
model settings. Give a read-only agent the agreed diff/files and the criteria
below; normalize its answer like any other reviewer.

## Review criteria for prompt-driven reviewers

For reviewers that take a prompt (`prompt` mode, chatgpt, Copilot, Claude
subagent), ask for real bugs, security issues and significant quality problems
in the agreed scope, one finding per bullet, with a priority tag and a
location:

```text
- [P2] Short imperative title — relative/path.ext:42-44
  One paragraph: what is wrong, why it matters, evidence. Optional
  "Fix: <concrete localized change>" when the remedy is clear.
```

P0/P1 = security, data loss, broken correctness; P2 = likely incorrect
behaviour, missing error handling, races; P3 = minor defects; Nit = style. Ask
for `No findings.` plus a one-sentence verdict when there is nothing to report.
Native Codex scope modes use Codex's built-in review prompt; do not append this
text to them.

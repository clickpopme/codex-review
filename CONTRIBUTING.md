# Contributing

## Layout

| Path | Purpose |
| --- | --- |
| `SKILL.md` | The skill Claude reads: Phases 0–9 and the safety rules |
| `references/` | Detail Claude reads on demand (backends, output format, config, Linear, troubleshooting) |
| `scripts/` | Two Bash helpers: `review-context.sh` (read-only repo probe) and `capture-review.sh` (runs Codex into a private run directory) |
| `examples/.codex-review.json` | Default configuration |
| `.claude-plugin/` | Plugin and marketplace manifests for `claude plugin install` |
| `tests/verify.py` | Offline checks |

## Running the checks

They need Python 3, PyYAML and ShellCheck; nothing is sent anywhere and no real
Codex review is run (a mock `codex` is used).

```sh
python3 -m venv .venv && . .venv/bin/activate
python -m pip install shellcheck-py PyYAML
python tests/verify.py
claude plugin validate .claude-plugin/plugin.json
claude plugin validate .claude-plugin/marketplace.json
```

`verify.py` creates throwaway Git repositories under a gitignored
`.verification/` directory in the checkout and checks:

- scope detection (any uncommitted change → `uncommitted`; clean tree → ask;
  a base branch is only offered when HEAD is ahead of it);
- repository slug parsing for SSH, HTTPS, `ssh://host:port`, `~user` and
  `file://` remotes; nested directories; detached and unborn HEAD;
- `capture-review.sh` against a mock Codex: `exec review` with `-o` and
  `--ephemeral`, model pinning, failure propagation, empty final message,
  version gate, ref verification, prompt mode, symlink and config validation;
- that both plain-install layouts contain every file `SKILL.md` links to;
- frontmatter, the ten Phase headings, JSON files, local Markdown links, and
  that no placeholders remain;
- ShellCheck on the scripts and on every ```` ```bash ```` fence in the docs
  (```` ```sh ```` fences are paste-into-terminal snippets and are not linted).

The same checks run in GitHub Actions on Ubuntu and macOS.

## Manual verification

The mock cannot prove anything about real Codex output. After changing the
helper or the parsing rules, run a real review on a small repository and
compare `final.txt` with the format in `references/output.md`. Behaviour was
last verified against Codex CLI 0.153.4 and Claude Code 2.1.

# codex-review

A [Claude Code](https://code.claude.com) skill that gets a second opinion on
your code from the [OpenAI Codex CLI](https://developers.openai.com/codex/cli/).
Ask Claude for a "codex review" and it will:

1. run `codex exec review` on your uncommitted changes (or a branch, or a commit),
2. read the findings and check each one against your code,
3. propose small, safe fixes for the minor ones, and
4. optionally turn the rest into Linear tickets.

Nothing is edited and no ticket is created until you approve a concrete plan.
Works with Claude Code's own review too — this is an extra, independent check
from a different model.

```text
You:    run codex review on my changes

Claude: Reviewer: Codex CLI 0.160.0 (your configured model). Scope: uncommitted
        changes on main — src/discount.js, src/users.js. Code and repository
        context will be sent to OpenAI under your Codex account.
        [a few minutes pass]
        3 findings:
          High   src/users.js:6     getUser returns passwordHash to callers   → manual
          Medium src/discount.js:2  loose == null lets "" through             → manual
          Low    src/discount.js:5  unused variable `total`                   → fix candidate
        Proposed fix 1: delete line 5 of src/discount.js. Checks: npm test.
        Reply proceed, details, or cancel.

You:    proceed

Claude: Applied fix 1; npm test passed before and after.
        Record: ~/.codex-reviews/pending/run.ab12cd34/
```

## Requirements

- Claude Code 2.x (the plugin install route needs plugin support, Claude Code 2.0+).
- macOS or Linux with Bash 3.2+, Git 2.24+ and jq 1.6+
  (`brew install jq` or `sudo apt-get install jq`).
- OpenAI Codex CLI **0.153.4 or newer**, signed in. Installing it needs Node.js 18+.
- Optional: a Linear MCP connection in Claude Code, if you want tickets.

## Install

### As a plugin (one command)

```sh
claude plugin marketplace add clickpopme/codex-review && claude plugin install codex-review@codex-review-marketplace
```

Restart Claude Code. The skill is available as `/codex-review:codex-review`
and triggers on natural requests such as "run codex review".

To try it from a local clone instead: `claude plugin marketplace add ./` from
inside the clone, then the same `claude plugin install …` command — or
`claude --plugin-dir .` to load it for one session without installing.

### As a plain skill

Clone or download this repository, then copy the four runtime items (not
`.claude-plugin/`) into a skills folder:

```sh
git clone https://github.com/clickpopme/codex-review.git
cd codex-review
```

Personal — available in all your projects:

```sh
mkdir -p ~/.claude/skills/codex-review
cp -R SKILL.md references scripts examples ~/.claude/skills/codex-review/
```

Project — shared with everyone who works on that repository (commit it):

```sh
mkdir -p /path/to/project/.claude/skills/codex-review
cp -R SKILL.md references scripts examples /path/to/project/.claude/skills/codex-review/
```

Restart Claude Code; the skill is `/codex-review`. Install it one way or the
other, not both.

## Set up Codex

```sh
npm install -g @openai/codex
codex login
codex login status
```

`codex login` opens a browser sign-in for a ChatGPT account. To use an API key
instead, with `OPENAI_API_KEY` already set in your shell:

```sh
printenv OPENAI_API_KEY | codex login --with-api-key
```

Never paste a key into chat or into this skill's config file. ChatGPT-login
usage and API billing differ; see
[OpenAI's authentication docs](https://developers.openai.com/codex/auth/).

## Using it

Open Claude Code inside the repository you want reviewed and ask:

- `run codex review` — reviews everything uncommitted (staged, unstaged and
  untracked files). If the tree is clean, Claude offers to compare against your
  base branch or review the last commit.
- `codex review against main` / `codex review the last commit`
- `codex review, just report` — findings only, no fix proposals
- `codex review, no tickets`

Codex has no "only staged files" or "only these paths" mode; if you ask for
that, Claude will explain and agree an alternative with you (usually a custom
instruction to the reviewer, which is advisory rather than enforced).

Before running, Claude lists the files in scope and flags untracked files and
anything that looks like a secret (`.env`, keys, tokens) so you can exclude
them. After the review you get the findings, a fix plan with the checks Claude
will run, and a prompt to reply `proceed`, `details` or `cancel`. Fixes are
made one at a time with a byte-exact backup first; Claude never stages,
commits, stashes or resets anything.

A review usually takes one to several minutes. Everything the run produced is
kept under `~/.codex-reviews/pending/run.…/` (see Privacy below).

## Configuration

Configuration is optional and lives in `.codex-review.json` at the root of the
repository being reviewed. Nothing is created unless you add it yourself: copy
[examples/.codex-review.json](examples/.codex-review.json) there and edit.
Commit it for team settings, or add it to that repository's `.gitignore` for
personal ones. Every option is described in
[references/config.md](references/config.md). The main ones:

- **Model** — by default Codex uses the model configured in your own Codex CLI
  (run `codex` and type `/model` to see what's available). To pin one for a
  repository set `review.model`; for a single run export
  `CODEX_REVIEW_MODEL=<id>` in the shell before starting `claude`.
- **What may be auto-fixed** — `auto_fix.max_severity` (default `Medium`;
  High findings are never auto-fixed), `auto_fix.skip_paths`, and whether the
  project's typecheck, lint or tests must pass before and after each fix.
- **Linear** — `skip_linear` is a top-level key and defaults to `true`. Set it
  to `false` and fill in `linear.team_key` to let Claude propose tickets.

## Optional: Linear tickets

Connect Linear to Claude Code first (for example with
[`claude mcp add`](https://code.claude.com/docs/en/mcp) and Linear's MCP
server, or a Linear connector if your setup provides one). This skill installs
no server of its own and does not depend on a particular one. Then set
`"skip_linear": false` and `linear.team_key` in `.codex-review.json`. The
default label is `codex-review`; create it in Linear or change `linear.labels`,
otherwise Claude will ask before creating it. Every ticket is shown to you in
full before it is created. Details: [references/linear.md](references/linear.md).

## Privacy

- **What leaves your machine.** Codex runs as an agent inside your repository.
  It is given the diff for the chosen scope, but it may open any other file in
  the working tree for context, and it also applies that repository's own
  `.codex/` config and `AGENTS.md` if you have marked the repository as trusted
  in Codex. All of that goes to OpenAI under your Codex account (or to whatever
  provider your Codex is configured for). Untracked files are part of the
  default scope, so an un-ignored `.env` or key file would be sent — Claude
  flags such files before running. Claude Code then handles the findings, so
  they go to Anthropic like the rest of your session. Approved ticket text
  goes to your Linear workspace.
- **What is stored locally.** Each run writes a private directory
  (`~/.codex-reviews/pending/run.…/`, mode 0700) holding Codex's output, the
  normalized findings and backups of any file that was fixed. These can
  contain source code; don't commit or share them, and delete them when you no
  longer need them. Confirmed Linear ticket IDs go to
  `~/.codex-reviews/ticketed.json`. Codex is run with `--ephemeral`, so it
  keeps no session file for the review, but it still writes its own logs
  under `~/.codex`.
- **No review runs without you asking for one**, and nothing is published.

## Troubleshooting

See [references/troubleshooting.md](references/troubleshooting.md). A failed or
interrupted review is always reported as failed, never as "no findings". The
findings are a model's opinion: they can be incomplete or wrong, which is why
each one is checked against the code and nothing is changed without you.

## Uninstall

Plain skill: delete the `codex-review` folder from `~/.claude/skills/` or the
project's `.claude/skills/`. Plugin:

```sh
claude plugin uninstall codex-review@codex-review-marketplace
claude plugin marketplace remove codex-review-marketplace
```

Repository config, `~/.codex-reviews/`, Codex itself and any Linear issues are
left alone.

## Contributing

Bug reports and pull requests are welcome. [CONTRIBUTING.md](CONTRIBUTING.md)
describes the offline test suite.

## License

[MIT](LICENSE) © clickpopme. This project is not affiliated with OpenAI or
Anthropic.

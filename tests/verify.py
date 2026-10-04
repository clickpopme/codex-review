#!/usr/bin/env python3
"""Offline checks for the codex-review skill.

Runs the helper scripts against throwaway Git repositories and a mock
`codex` executable, validates metadata and local links, and ShellChecks the
runtime scripts plus every ```bash fence in the documentation. All scratch
data stays under .verification/ inside this checkout. No real review is run.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / '.verification'
SCRATCH.mkdir(exist_ok=True)
BASH = os.environ.get('TEST_BASH', '/bin/bash')

# Isolate fixture Git operations from the developer's global config and hooks.
GIT_ENV = {'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}


def run(args, cwd=ROOT, ok=True, env=None):
    merged = {**os.environ, **GIT_ENV, **(env or {})}
    p = subprocess.run(args, cwd=cwd, env=merged, text=True, capture_output=True)
    if ok and p.returncode:
        raise AssertionError(f'{args[0]} failed ({p.returncode}): {p.stdout}{p.stderr}')
    return p


def git(repo, *args):
    return run(['git', '-c', 'user.name=Fixture', '-c',
                'user.email=fixture@example.invalid', *args], cwd=repo).stdout.strip()


def context(repo):
    return json.loads(run([BASH, str(ROOT / 'scripts/review-context.sh'), str(repo)]).stdout)


MOCK_CODEX = '''#!/usr/bin/env bash
set -eu
case "${1-}" in
  --version) printf 'codex-cli %s\\n' "${MOCK_VERSION:-0.153.4}"; exit 0 ;;
esac
if [ "${1-}" = exec ] && [ "${2-}" = review ] && [ "${3-}" = --help ]; then
  printf '%s\\n' '--config --uncommitted --base --commit --output-last-message --ephemeral'
  exit 0
fi
printf '%s\\n' "$@" > "$MOCK_ARGS"
out=''
while [ $# -gt 0 ]; do
  if [ "$1" = -o ]; then out=$2; shift; fi
  shift
done
if [ -n "$out" ] && [ "${MOCK_EMPTY_FINAL:-0}" != 1 ]; then
  printf '%s\\n' 'Full review comments:' '' '- [P2] Example finding — /tmp/example.js:3-4' '  Body.' > "$out"
fi
printf '%s\\n' 'final output'
printf '%s\\n' 'diagnostic' >&2
exit "${MOCK_STATUS:-0}"
'''

with tempfile.TemporaryDirectory(prefix='verify-', dir=SCRATCH) as directory:
    work = Path(directory)
    repo = work / 'repo with spaces'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'symbolic-ref', 'HEAD', 'refs/heads/main')
    (repo / 'file.txt').write_text('baseline\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'fixture')
    ctx = context(repo)
    assert ctx['default_scope'] == 'ask'
    assert ctx['candidate_base'] == '', ctx   # on main itself: nothing to compare
    assert ctx['repo'] == repo.name
    print('scope: clean tree on main -> ask; no base candidate offered')

    for name in ['one.py', 'config.json', 'README.md', 'package-lock.json', 'space name.py', 'line\nbreak.py']:
        path = repo / name
        path.write_text('uncommitted\n')
        assert context(repo)['default_scope'] == 'uncommitted'
        print('scope:', repr(name), 'alone -> uncommitted')
        path.unlink()
    (repo / 'file.txt').write_text('staged\n')
    git(repo, 'add', 'file.txt')
    assert context(repo)['default_scope'] == 'uncommitted'
    print('scope: staged-only -> uncommitted')
    git(repo, 'commit', '-qm', 'staged fixture')

    git(repo, 'checkout', '-q', '-b', 'feature')
    (repo / 'feature.txt').write_text('feature\n')
    git(repo, 'add', 'feature.txt')
    git(repo, 'commit', '-qm', 'feature work')
    ctx = context(repo)
    assert ctx['candidate_base'] == 'main' and ctx['commits_ahead_of_base'] == 1, ctx
    print('scope: feature branch ahead of main -> candidate base main')
    git(repo, 'checkout', '-q', 'main')
    git(repo, 'checkout', '--detach', '-q')
    assert context(repo)['branch'] == 'HEAD'
    print('scope: detached HEAD -> valid context')

    cases = [
        ('git@github.com:owner/repo.git', 'owner/repo'),
        ('git@github.com:owner/repo', 'owner/repo'),
        ('https://github.com/owner/repo.git', 'owner/repo'),
        ('https://github.com/owner/repo', 'owner/repo'),
        ('ssh://git@example.invalid:2222/group/sub/repo.git', 'group/sub/repo'),
        ('ssh://host.example/~me/repo.git', 'me/repo'),
        ('file:///tmp/x', repo.name),
    ]
    for remote, expected in cases:
        git(repo, 'config', 'remote.origin.url', remote)
        got = context(repo)['repo']
        assert got == expected, (remote, got)
        print('slug:', remote, '->', got)
    git(repo, 'config', '--unset', 'remote.origin.url')
    child = repo / 'nested'
    child.mkdir()
    assert context(child)['root'] == str(repo)
    print('anchor: nested cwd -> repository root; no remote -> basename')

    unborn = work / 'unborn'
    unborn.mkdir()
    git(unborn, 'init', '-q')
    assert run([BASH, str(ROOT / 'scripts/review-context.sh'), str(unborn)], ok=False).returncode != 0
    print('scope: unborn HEAD -> explicit failure')

    # The mock exercises invocation and capture only; it is not real model output.
    bin_dir = work / 'bin'
    bin_dir.mkdir()
    fake = bin_dir / 'codex'
    fake.write_text(MOCK_CODEX)
    fake.chmod(0o700)
    env = dict(PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
               MOCK_ARGS=str(work / 'args.txt'), CODEX_REVIEW_MODEL='')
    pending = work / 'pending'
    command = [BASH, str(ROOT / 'scripts/capture-review.sh'), str(repo), 'uncommitted', '', str(pending)]

    # No config file at all is fine.
    first = Path(run(command, env=env).stdout.strip())
    second = Path(run(command, env=env).stdout.strip())
    assert first != second
    assert (first / 'stdout.txt').read_text() == 'final output\n'
    assert (first / 'stderr.txt').read_text() == 'diagnostic\n'
    assert (first / 'final.txt').read_text().startswith('Full review comments:')
    assert (first.stat().st_mode & 0o777) == 0o700
    assert ((first / 'final.txt').stat().st_mode & 0o777) == 0o600
    status = json.loads((first / 'status.json').read_text())
    assert status['exit_code'] == 0 and status['final'] == 'final.txt'
    args = (work / 'args.txt').read_text().splitlines()
    assert args[:2] == ['exec', 'review'] and '--ephemeral' in args and '-o' in args
    assert '--uncommitted' in args and not any(x.startswith('model=') for x in args)
    print('capture: no config -> defaults, exec review, -o final.txt, --ephemeral -> PASS')

    shutil.copyfile(ROOT / 'examples/.codex-review.json', repo / '.codex-review.json')
    pinned = dict(env, CODEX_REVIEW_MODEL='chosen-model')
    run(command, env=pinned)
    text = (work / 'args.txt').read_text()
    assert 'model="chosen-model"' in text and 'review_model="chosen-model"' in text
    failed = run(command, ok=False, env=dict(env, MOCK_STATUS='7'))
    assert failed.returncode == 7
    assert json.loads((Path(failed.stdout.strip()) / 'status.json').read_text())['exit_code'] == 7
    empty = run(command, ok=False, env=dict(env, MOCK_EMPTY_FINAL='1'))
    assert empty.returncode == 1 and 'no final message' in empty.stderr
    old = run(command, ok=False, env=dict(env, MOCK_VERSION='0.100.0'))
    assert old.returncode != 0 and '0.153.4' in old.stderr
    scoped = command.copy()
    scoped[3:5] = ['base', 'main']
    run(scoped, env=env)
    assert ['--base', 'main'] == (work / 'args.txt').read_text().splitlines()[-3:-1][:2] or \
        '--base' in (work / 'args.txt').read_text()
    assert 'main\n' in (work / 'args.txt').read_text()   # ref name passed, not a SHA
    scoped[3:5] = ['commit', 'HEAD']
    run(scoped, env=env)
    assert git(repo, 'rev-parse', 'HEAD') in (work / 'args.txt').read_text()
    scoped[3:5] = ['base', 'no-such-ref']
    assert run(scoped, ok=False, env=env).returncode != 0
    prompt = work / 'prompt.txt'
    prompt.write_text('Review the agreed scope.\n')
    prompted = command.copy()
    prompted[3:5] = ['prompt', str(prompt)]
    run(prompted, env=env)
    assert (work / 'args.txt').read_text().splitlines()[-1] == '-'
    assert run(command, ok=False, env=dict(env, CODEX_REVIEW_MODEL='$(false)')).returncode != 0
    bad = command.copy()
    bad[3:5] = ['uncommitted', 'stray']
    assert 'VALUE must be empty' in run(bad, ok=False, env=env).stderr
    config_path = repo / '.codex-review.json'
    config_path.unlink()
    config_path.symlink_to(ROOT / 'examples/.codex-review.json')
    assert run(command, ok=False, env=env).returncode != 0
    config_path.unlink()
    config_path.write_text('[]\n')
    assert 'Invalid' in run(command, ok=False, env=env).stderr
    config_path.unlink()
    slashed = command.copy()
    slashed[5] = str(pending) + '/'
    assert 'normalized' in run(slashed, ok=False, env=env).stderr
    print('capture: model pins, failure status, empty final, old version, refs, prompt stdin, bad config, symlinks -> PASS')

    # Plain installation contents and links are independent of installed location.
    for destination in [work / 'personal/.claude/skills/codex-review', work / 'project/.claude/skills/codex-review']:
        destination.mkdir(parents=True)
        shutil.copyfile(ROOT / 'SKILL.md', destination / 'SKILL.md')
        for component in ['references', 'scripts', 'examples']:
            shutil.copytree(ROOT / component, destination / component)
        for target in re.findall(r'\]\(([^)]+)\)', (destination / 'SKILL.md').read_text()):
            if '://' in target:
                continue
            assert (destination / target).exists(), target
        assert run([BASH, str(destination / 'scripts/review-context.sh'), str(repo)]).returncode == 0
    print('install: personal and project layouts resolve every SKILL.md reference and run the helper -> PASS')

# Validate local Markdown links; no external requests.
for path in ROOT.rglob('*.md'):
    if '.verification' in path.parts or '.venv' in path.parts:
        continue
    prose = re.sub(r'```.*?```|`[^`]*`', '', path.read_text(), flags=re.S)
    for link in re.findall(r'\]\(([^)]+)\)', prose):
        if '://' in link or link.startswith('#'):
            continue
        assert (path.parent / link.split('#')[0]).exists(), (path.name, link)
frontmatter = yaml.safe_load((ROOT / 'SKILL.md').read_text().split('---', 2)[1])
assert {'name', 'description'} <= set(frontmatter), frontmatter
name = str(frontmatter['name'])
description = str(frontmatter['description'])
assert re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) and len(name) <= 64
assert 0 < len(description) <= 1024
assert len(re.findall(r'^## Phase [0-9] ', (ROOT / 'SKILL.md').read_text(), re.M)) == 10
for path in [ROOT / 'examples/.codex-review.json', *(ROOT / '.claude-plugin').glob('*.json')]:
    json.loads(path.read_text())
for text in [ROOT / 'LICENSE', ROOT / 'README.md', *(ROOT / '.claude-plugin').glob('*.json')]:
    assert '<YOUR NAME>' not in text.read_text() and 'YOUR-ACCOUNT' not in text.read_text(), text
print('metadata: frontmatter, phases 0-9, JSON, local links, no placeholders -> PASS')

# ShellCheck the runtime scripts and every ```bash fence (```sh fences are
# paste-into-terminal snippets and are not linted).
checker = shutil.which('shellcheck')
if checker:
    snippets = []
    with tempfile.TemporaryDirectory(prefix='snippets-', dir=SCRATCH) as directory:
        for path in [ROOT / 'SKILL.md', ROOT / 'README.md', ROOT / 'CONTRIBUTING.md', *(ROOT / 'references').glob('*.md')]:
            for i, body in enumerate(re.findall(r'```bash\n(.*?)\n```', path.read_text(), re.S)):
                snippet = Path(directory) / f'{path.stem}-{i}.sh'
                snippet.write_text('#!/usr/bin/env bash\n' + body + '\n')
                snippets.append(str(snippet))
        run([checker, '-s', 'bash', *map(str, (ROOT / 'scripts').glob('*.sh')), *snippets])
    print(f'ShellCheck: runtime scripts and {len(snippets)} extracted bash snippets -> PASS')
else:
    print('ShellCheck: unavailable (install and rerun; not a pass)')

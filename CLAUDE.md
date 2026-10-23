## Tests

Run `make ci` (ruff lint and format, mypy, pytest with coverage; needs `uv`). For one file: `uv run pytest tests/test_x.py`. `make fix` applies ruff's auto-fixes.

## Agent skills

### Issue tracker

GitHub Issues at `StanleyGoldman/immich-folder-organizer`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Skill sources

All agent skills come from the `mattpocock-skills` plugin, enabled at project level in `.claude/settings.json`. None are vendored in the repo.

## Worktrees

- The main checkout in the repo folder belongs to the user. Leave its branch as the user left it.
- Do branch work (fixes, features, doc updates, PR branches) in a git worktree under `.claude/worktrees/<name>` (gitignored), never beside the repo folder, branched from `origin/main`. A subagent in its own worktree can carry such a change in the background.
- In a worktree-isolated subagent, run each shell command as one plain call with literal paths. Claude Code's worktree isolation guard refuses any command it can't prove keeps git inside the worktree. Backgrounding, loops, shell variables, `sh <script>`, and inline text containing backticks or `$` all trip it. Write PR bodies to a scratchpad file and pass `--body-file`; write commit messages to a file and pass `git commit -F <file>`.

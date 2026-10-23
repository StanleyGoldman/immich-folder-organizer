# CI

Woodpecker runs `.woodpecker/ci.yml` on every pull request and on every push to `main`, on the oldhermit agents. On a pull request it also posts a stats comment. A pull request can't merge into `main` until the check passes.

## Running the checks locally

```sh
make ci        # ruff lint, ruff format --check, mypy, pytest with coverage
make fix       # apply ruff's auto-fixes and formatting
make image     # build the production image (needs Docker)
uv run pytest tests/test_x.py   # one test file
```

The Makefile is the single entry point. Every CI step runs a Makefile target, so a green `make ci` predicts a green pipeline. Each check writes `reports/<check>.log` and `reports/<check>.status`, and the report step reads those files.

## Pipeline

| Step | Runs | Events |
|---|---|---|
| `ci-image` | builds `immich-folder-organizer-ci:latest` from `.woodpecker/Dockerfile` | all |
| `lint` | `make -k lint format` | all |
| `types` | `make types` | all |
| `test` | `make -k test coverage-diff coverage-base BASE=origin/<target>` | pull request |
| `test-main` | `make test` | push to `main` |
| `image` | `make image TAG=<pipeline number>` | all |
| `report` | `python3 scripts/ci/pr_report.py` | pull request, even when checks fail |

- **CI image:** `python:3.11-slim` with git, make, uv 0.13.5 and the Docker CLI. It is built on oldhermit's Docker daemon through `socket-proxy` (`DOCKER_BUILDKIT=0`), and it is never pushed to a registry. It holds tools only. Each step installs the project's dependencies from `uv.lock`, so concurrent PRs never share dependencies.
- **uv cache:** `/cache/agent/immich-folder-organizer/uv`. `/cache/agent` is a per-host directory that every oldhermit agent mounts. `UV_LOCKED=1` makes a stale `uv.lock` fail the step instead of being rewritten.
- **Coverage deltas:** `coverage-base` runs the suite at the merge-base in a worktree outside the checkout. If the base predates uv (it has no `uv.lock`), the report shows "n/a" and omits the deltas.
- **uv version:** pinned to 0.13.5 in the CI image, the production `Dockerfile` and the devcontainer. Bump all three together.

## The PR comment

`scripts/ci/pr_report.py` renders a comment containing:
- the check results;
- changed-line and total coverage (🟢 at 80% or above, 🟡 at 60% or above, 🔴 below);
- per-file changed-line coverage with the uncovered lines;
- the PR's size;
- the first 40 lines of each failing check's output (the last 40 for tests and the image).

The comment starts with the marker `<!-- immich-folder-organizer-ci -->`. On each run, the script deletes every earlier comment that carries the marker and was posted by the token's own user, then posts a new one. Comments from anyone else are never touched.

## Secret: `github_token`

The report step posts with a fine-grained GitHub PAT, scoped to this repository only, with **Pull requests: Read and write**. `Issues: write` alone is refused, even though PR comments go through the issues API. The secret is available to `pull_request` events only. Store it from a file so the token never appears on a command line:

```sh
woodpecker-cli repo secret add --repository StanleyGoldman/immich-folder-organizer \
  --name github_token --event pull_request --value @/path/to/pat.txt
```

The script strips the trailing newline that a file-stored secret keeps. When GitHub refuses a request, the step log shows GitHub's message and its `x-accepted-github-permissions` header.

## Required check and ruleset

Woodpecker names the check after the workflow file: `ci/woodpecker/pr/ci`. The `Main` ruleset requires that check on the default branch. It also blocks deleting the branch and force-pushing to it, and it requires a pull request (with 0 approvals). **Renaming `ci.yml` leaves every PR waiting on a check that never arrives.** For the same reason, the workflow has no path filter.

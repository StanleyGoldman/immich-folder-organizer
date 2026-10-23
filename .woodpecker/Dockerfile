# Tools for every check step in .woodpecker/ci.yml; project dependencies come
# from uv.lock in each step. Built on oldhermit's Docker daemon by the
# `ci-image` step, tagged immich-folder-organizer-ci:latest, never pushed.
FROM python:3.11-slim

# git: diff-cover and the merge-base worktree; make: every step's entry point
RUN apt-get update && apt-get install -y --no-install-recommends git make && \
    rm -rf /var/lib/apt/lists/* && \
    git config --system --add safe.directory '*'

# Same uv as the production Dockerfile and the devcontainer
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
# Docker CLI for `make image`, talking to the daemon through socket-proxy
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker

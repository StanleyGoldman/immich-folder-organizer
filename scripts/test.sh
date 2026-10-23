#!/usr/bin/env bash
# Run the test suite in the production Python image (python:3.11-slim).
# Arguments pass through to pytest: scripts/test.sh -q tests/test_orchestrator.py
set -euo pipefail

cd "$(dirname "$0")/.."

docker run --rm \
  -v "$PWD":/app -w /app \
  -v immich-folder-organizer-pip-cache:/root/.cache/pip \
  python:3.11-slim \
  sh -c 'pip install -q --root-user-action=ignore --disable-pip-version-check -r requirements.txt \
    && python -m pytest "$@"' pytest "$@"

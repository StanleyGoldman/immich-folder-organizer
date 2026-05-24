#!/usr/bin/env bash
# Post-create setup for the devcontainer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# --- Fix ownership of named volumes ---
# Must happen before Claude install; the claude-code-config volume is
# mounted at ~/.claude and is initially owned by root.
sudo chown node /home/node/.claude
sudo chown node /commandhistory

# --- Persist .claude.json on the volume ---
# Claude Code needs both .credentials.json AND .claude.json for auth.
# .credentials.json lives inside ~/.claude/ (on the volume), but .claude.json
# lives at ~/.claude.json (in the home dir, wiped on rebuild).
# Symlink it to the volume so it survives rebuilds.
CLAUDE_JSON_LINK="/home/node/.claude.json"
CLAUDE_JSON_PERSISTENT="/home/node/.claude/claude-config.json"

if [ -f "$CLAUDE_JSON_LINK" ] && [ ! -L "$CLAUDE_JSON_LINK" ]; then
	mv "$CLAUDE_JSON_LINK" "$CLAUDE_JSON_PERSISTENT"
fi

ln -sf "$CLAUDE_JSON_PERSISTENT" "$CLAUDE_JSON_LINK"

# --- Install Claude Code CLI ---
if ! command -v claude >/dev/null 2>&1; then
	curl -fsSL https://claude.ai/install.sh | bash
else
	echo "Claude CLI already installed: $(which claude)"
fi

# --- Git safe directories for the workspace and any worktrees ---
git config --global --add safe.directory /workspace/immich-folder-organizer
git config --global --add safe.directory '/workspace/*'

# --- Install Python dependencies into the pre-created venv ---
if [ -f requirements.txt ]; then
	uv pip install --python /workspace/immich-folder-organizer/.venv/bin/python -r requirements.txt
fi

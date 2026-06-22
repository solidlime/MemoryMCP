#!/bin/bash
# Setup agent-browser for MemoryMCP (run at container startup)
set -e

AGENT_DIR="${AGENT_BROWSER_DIR:-/opt/memory-mcp/data/agent-browser}"
AGENT_BROWSER="$AGENT_DIR/bin/agent-browser"
DATA_ROOT="${MEMORY_MCP_DATA_ROOT:-/opt/memory-mcp/data}"
export PATH="$AGENT_DIR/bin:$PATH"

# ── Step 1: Install agent-browser CLI ──
if command -v agent-browser &>/dev/null; then
    echo "[agent-browser] CLI already available: $(agent-browser --version)"
else
    echo "[agent-browser] Installing CLI to $AGENT_DIR..."
    mkdir -p "$AGENT_DIR"
    npm install -g agent-browser --prefix "$AGENT_DIR" 2>&1 | tail -3
    echo "[agent-browser] CLI installed: $($AGENT_BROWSER --version)"
fi

# ── Step 2: Persist Chrome cache to volume via symlink ──
# agent-browser stores Chrome under $HOME/.agent-browser/browsers,
# which is lost on container restart. Symlink to the data volume so
# Chrome survives restarts and doesn't re-download.
AGENT_HOME="$DATA_ROOT/.agent-browser"
if [ ! -L "$HOME/.agent-browser" ]; then
    mkdir -p "$AGENT_HOME"
    if [ -d "$HOME/.agent-browser" ] && [ ! -L "$HOME/.agent-browser" ]; then
        mv "$HOME/.agent-browser"/* "$AGENT_HOME/" 2>/dev/null || true
        rm -rf "$HOME/.agent-browser"
    fi
    ln -sfn "$AGENT_HOME" "$HOME/.agent-browser"
fi

# ── Step 3: Ensure Chrome is installed (idempotent) ──
echo "[agent-browser] Ensuring Chrome is available..."
"$AGENT_BROWSER" install 2>&1 | tail -5

echo "[agent-browser] Setup complete: $($AGENT_BROWSER --version)"

exec "$@"

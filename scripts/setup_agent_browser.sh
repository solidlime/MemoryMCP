#!/bin/bash
# Setup agent-browser for MemoryMCP (run at container startup)
set -eo pipefail

AGENT_DIR="${AGENT_BROWSER_DIR:-/opt/memory-mcp/data/agent-browser}"
AGENT_BROWSER="$AGENT_DIR/bin/agent-browser"
DATA_ROOT="${MEMORY_MCP_DATA_ROOT:-/opt/memory-mcp/data}"
export PATH="$AGENT_DIR/bin:$PATH"

# ── Step 1: Install agent-browser CLI ──
# Verify the binary actually works (not just exists — host-installed binaries
# may reference node paths from nvm that don't exist in the container).
if AGENT_VERSION=$("$AGENT_BROWSER" --version 2>/dev/null) && [ -n "$AGENT_VERSION" ]; then
    echo "[agent-browser] CLI already available: $AGENT_VERSION"
else
    echo "[agent-browser] Installing CLI to $AGENT_DIR (stale/missing binary)..."
    # Wipe any stale host-installed files that npm refuses to overwrite
    rm -rf "$AGENT_DIR"
    mkdir -p "$AGENT_DIR"
    npm install -g agent-browser --prefix "$AGENT_DIR" 2>&1 | tail -3
    AGENT_VERSION=$("$AGENT_BROWSER" --version 2>/dev/null)
    echo "[agent-browser] CLI installed: $AGENT_VERSION"
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

# ── Step 3: Ensure Chrome is installed (idempotent, background) ──
# Run Chrome install in background with low CPU/IO priority to avoid
# starving the MCP server during first-time setup (~200MB download).
AGENT_LOG="$DATA_ROOT/agent-browser-install.log"
echo "[agent-browser] Chrome install starting in background (log: $AGENT_LOG)..."
nice -n 19 ionice -c 3 "$AGENT_BROWSER" install > "$AGENT_LOG" 2>&1 &
# Record PID so server can poll readiness if needed
echo $! > /tmp/agent-browser-install.pid

echo "[agent-browser] Server starting (Chrome will be ready shortly)..."
echo "[agent-browser] version: $($AGENT_BROWSER --version)"

exec "$@"

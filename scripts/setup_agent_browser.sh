#!/bin/bash
# Setup agent-browser for MemoryMCP (run at container startup)
set -e

AGENT_DIR="${AGENT_BROWSER_DIR:-/opt/memory-mcp/data/agent-browser}"
export PATH="$AGENT_DIR/bin:$PATH"

if command -v agent-browser &>/dev/null; then
    echo "[agent-browser] Already available: $(agent-browser --version)"
    exec "$@"
fi

echo "[agent-browser] Installing to $AGENT_DIR..."
mkdir -p "$AGENT_DIR"

# Install agent-browser
npm install -g agent-browser --prefix "$AGENT_DIR" 2>&1 | tail -3

# Install Chrome
"$AGENT_DIR/bin/agent-browser" install 2>&1 | tail -5

echo "[agent-browser] Setup complete: $($AGENT_DIR/bin/agent-browser --version)"

exec "$@"

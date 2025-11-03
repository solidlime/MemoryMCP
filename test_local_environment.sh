#!/bin/bash
# test_local_environment.sh
# Local environment test script for Memory MCP
# Tests: Qdrant startup -> MCP server startup -> Health check -> Log verification

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
QDRANT_PORT=6333
MCP_PORT=26262
LOG_FILE="/tmp/mcp_server_test.log"
PID_FILE="/tmp/mcp_server_test.pid"

echo -e "${GREEN}🧪 Memory MCP Local Environment Test${NC}"
echo "========================================"
echo ""

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
    
    # Stop MCP server if running
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Stopping MCP server (PID: $PID)..."
            kill $PID
            sleep 2
        fi
        rm -f "$PID_FILE"
    fi
    
    # Stop Qdrant container (Docker)
    echo "Stopping Qdrant container..."
    if docker ps --format '{{.Names}}' | grep -q '^qdrant$'; then
        docker stop qdrant
        echo "Qdrant container stopped"
    else
        echo "Qdrant container not running"
    fi
    
    echo -e "${GREEN}✅ Cleanup complete${NC}"
    echo -e "${YELLOW}💡 Note: Qdrant container is stopped but not removed${NC}"
    echo -e "${YELLOW}💡 To remove: docker rm qdrant${NC}"
    echo -e "${YELLOW}💡 To remove data: rm -rf ./data/qdrant_storage${NC}"
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

# Step 1: Start Qdrant
echo -e "${YELLOW}📦 Step 1: Starting Qdrant (Docker)...${NC}"

# Check if Qdrant container exists
if docker ps -a --format '{{.Names}}' | grep -q '^qdrant$'; then
    echo "Qdrant container found, starting..."
    docker start qdrant
else
    echo "Creating new Qdrant container..."
    docker run -d \
        --name qdrant \
        -p 6333:6333 \
        -p 6334:6334 \
        -v $(pwd)/data/qdrant_storage:/qdrant/storage \
        qdrant/qdrant:latest
fi

sleep 3

# Verify Qdrant is running
if ! docker ps --format '{{.Names}}' | grep -q '^qdrant$'; then
    echo -e "${RED}❌ Qdrant container not running${NC}"
    echo "Container status:"
    docker ps -a | grep qdrant || echo "No qdrant container found"
    exit 1
fi

echo -e "${GREEN}✅ Qdrant started (Docker container)${NC}"

# Check Qdrant health
echo -e "${YELLOW}🔍 Checking Qdrant health...${NC}"
if curl -s "http://localhost:$QDRANT_PORT/health" > /dev/null; then
    echo -e "${GREEN}✅ Qdrant is healthy${NC}"
else
    echo -e "${RED}❌ Qdrant health check failed${NC}"
    exit 1
fi

# Step 2: Start MCP Server
echo -e "\n${YELLOW}🚀 Step 2: Starting MCP Server...${NC}"
cd /home/rausraus/memory-mcp
source venv-rag/bin/activate

# Start server in background
python memory_mcp.py > "$LOG_FILE" 2>&1 &
MCP_PID=$!
echo $MCP_PID > "$PID_FILE"

echo "MCP Server PID: $MCP_PID"
echo "Log file: $LOG_FILE"

# Wait for server to initialize
echo -e "${YELLOW}⏳ Waiting for server initialization...${NC}"
echo "Monitoring startup logs:"
echo "------------------------"

# Monitor logs for 30 seconds max
COUNTER=0
MAX_WAIT=40
INITIALIZED=false

while [ $COUNTER -lt $MAX_WAIT ]; do
    if [ -f "$LOG_FILE" ]; then
        # Show recent log lines
        tail -5 "$LOG_FILE" | grep -v "^$"
        
        # Check if server is ready
        if grep -q "Application startup complete" "$LOG_FILE"; then
            INITIALIZED=true
            break
        fi
        
        # Check for errors
        if grep -q "Failed to initialize" "$LOG_FILE"; then
            echo -e "${RED}❌ Server initialization failed${NC}"
            echo "Error logs:"
            grep "Failed to initialize" "$LOG_FILE"
            exit 1
        fi
    fi
    
    sleep 2
    COUNTER=$((COUNTER + 2))
    echo "... waiting ($COUNTER/$MAX_WAIT seconds)"
done

if [ "$INITIALIZED" = false ]; then
    echo -e "${RED}❌ Server failed to initialize in time${NC}"
    echo "Last 20 lines of log:"
    tail -20 "$LOG_FILE"
    exit 1
fi

echo -e "${GREEN}✅ MCP Server initialized${NC}"

# Step 3: Health Check
echo -e "\n${YELLOW}🏥 Step 3: Health Check...${NC}"
sleep 2

HEALTH_RESPONSE=$(curl -s "http://localhost:$MCP_PORT/health")
if [ -n "$HEALTH_RESPONSE" ]; then
    echo "Health endpoint response:"
    echo "$HEALTH_RESPONSE" | jq . || echo "$HEALTH_RESPONSE"
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${RED}❌ Health check failed${NC}"
    exit 1
fi

# Step 4: MCP Initialize Test
echo -e "\n${YELLOW}🔌 Step 4: MCP Initialize Request...${NC}"

INIT_RESPONSE=$(curl -s -X POST "http://localhost:$MCP_PORT/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Persona: default" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    }
  }')

if echo "$INIT_RESPONSE" | grep -q "serverInfo"; then
    echo "Initialize response:"
    echo "$INIT_RESPONSE" | grep "data:" | sed 's/data: //' | jq . || echo "$INIT_RESPONSE"
    echo -e "${GREEN}✅ MCP Initialize successful${NC}"
else
    echo -e "${RED}❌ MCP Initialize failed${NC}"
    echo "Response: $INIT_RESPONSE"
    exit 1
fi

# Summary
echo -e "\n${GREEN}🎉 All tests passed!${NC}"
echo "========================================"
echo "Qdrant:     ✅ Running on port $QDRANT_PORT"
echo "MCP Server: ✅ Running on port $MCP_PORT (PID: $MCP_PID)"
echo "Logs:       $LOG_FILE"
echo ""
echo -e "${YELLOW}💡 Tip: Server will be stopped when you exit this script${NC}"
echo -e "${YELLOW}💡 To view logs: tail -f $LOG_FILE${NC}"
echo ""
echo "Press Ctrl+C to stop and cleanup..."

# Keep running until interrupted
wait $MCP_PID

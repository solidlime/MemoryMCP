# Testing Guide - Memory MCP

This document describes how to test Memory MCP locally before deploying to production.

## ⚠️ Important: Local Testing Only

**All tests MUST be run locally, never in production (NAS) environment.**

## Prerequisites

- Docker & Docker Compose (for Qdrant)
- Python 3.12+ with venv
- `jq` command (for JSON parsing in bash scripts)

```bash
# Install jq if needed
sudo apt-get install jq
```

## Quick Start

### 1. Full Environment Test (Recommended)

This script will:
- Start Qdrant container
- Launch MCP server in background
- Verify health endpoint
- Test MCP initialize
- Keep server running until you press Ctrl+C

```bash
./test_local_environment.sh
```

**Output:**
```
🧪 Memory MCP Local Environment Test
========================================

📦 Step 1: Starting Qdrant...
✅ Qdrant started
✅ Qdrant is healthy

🚀 Step 2: Starting MCP Server...
MCP Server PID: 12345
⏳ Waiting for server initialization...
✅ MCP Server initialized

🏥 Step 3: Health Check...
✅ Health check passed

🔌 Step 4: MCP Initialize Request...
✅ MCP Initialize successful

🎉 All tests passed!
```

**Cleanup:**
- Press `Ctrl+C` to stop server and Qdrant
- Automatic cleanup on exit

### 2. HTTP MCP Endpoint Test

After starting the server with `test_local_environment.sh`, run this in another terminal:

```bash
# Activate venv
source venv-rag/bin/activate

# Run HTTP endpoint tests
python test_mcp_http.py
```

**Output:**
```
🧪 MCP HTTP Endpoint Test Suite
============================================================

🏥 Testing health endpoint...
  ✅ Health: ok, Persona: default

🔌 Testing MCP initialize...
  ✅ Initialize: Memory Service v1.19.0

🔧 Testing tools/list...
  ✅ Found 5 tools:
     - create_memory
     - read_memory
     - search_memory
     - delete_memory
     - get_session_context

📋 Testing get_session_context...
  ✅ Session context retrieved

💾 Testing create_memory...
  ✅ Memory created: memory_20251103123456

🔍 Testing read_memory...
  ✅ Found 3 memories

🔎 Testing search_memory...
  ✅ Found 2 memories

🗑️  Testing delete_memory...
  ✅ Memory deleted successfully

📊 Test Summary
============================================================
✅ PASS - Health Check
✅ PASS - MCP Initialize
✅ PASS - List Tools
✅ PASS - Get Session Context
✅ PASS - Create Memory
✅ PASS - Read Memory
✅ PASS - Search Memory
✅ PASS - Delete Memory
------------------------------------------------------------
Total: 8/8 passed (100.0%)
```

## Manual Testing

### Start Components Individually

#### 1. Start Qdrant

```bash
docker-compose up -d qdrant

# Verify
curl http://localhost:6333/health
```

#### 2. Start MCP Server

```bash
source venv-rag/bin/activate
python memory_mcp.py
```

Wait for:
```
✅ RAG system initialized successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:26262
```

#### 3. Test Health Endpoint

```bash
curl http://localhost:26262/health | jq .
```

Expected:
```json
{
  "status": "ok",
  "persona": "default",
  "time": "2025-11-03T12:34:56.789012"
}
```

#### 4. Test MCP Initialize

```bash
curl -X POST http://localhost:26262/mcp \
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
  }'
```

Expected response:
```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05",...}}
```

#### 5. Test Tool Calls

##### List Available Tools

```bash
curl -X POST http://localhost:26262/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Persona: default" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

##### Call create_memory

```bash
curl -X POST http://localhost:26262/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Persona: default" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "create_memory",
      "arguments": {
        "content_or_query": "Test memory from curl",
        "importance": 0.7
      }
    }
  }'
```

## Debugging

### View Server Logs

If using `test_local_environment.sh`:
```bash
tail -f /tmp/mcp_server_test.log
```

If running manually:
```bash
# Server logs are in stdout
# Or check operation logs:
tail -f data/logs/memory_operations.log
```

### Check Qdrant Status

```bash
# List running containers
docker ps | grep qdrant

# Check Qdrant collections
curl http://localhost:6333/collections | jq .

# View specific collection
curl http://localhost:6333/collections/memory_default | jq .
```

### Check Database

```bash
# SQLite database location
ls -la memory/default/memories.db

# Query database
sqlite3 memory/default/memories.db "SELECT COUNT(*) FROM memories;"
```

## Troubleshooting

### Error: "Qdrant container not running"

```bash
# Check Docker
docker ps -a | grep qdrant

# Restart
docker-compose restart qdrant
```

### Error: "Failed to initialize RAG system"

Check logs for specific model loading errors:

```bash
grep -i "failed to initialize" /tmp/mcp_server_test.log
```

Common causes:
- Missing `sentencepiece` dependency → `pip install sentencepiece`
- CUDA issues → Verify `embeddings_device=cpu` in config
- Network issues → Check HuggingFace model download

### Error: "Port already in use"

```bash
# Find process using port 26262
lsof -i :26262

# Kill if needed
kill -9 <PID>
```

### Error: "MCP initialize timeout"

- Server may still be loading models
- Wait for "Application startup complete" in logs
- Check for errors in initialization phase

## Test Coverage

| Component | Test Script | Coverage |
|-----------|-------------|----------|
| Qdrant Startup | `test_local_environment.sh` | ✅ |
| MCP Server Startup | `test_local_environment.sh` | ✅ |
| Health Endpoint | Both scripts | ✅ |
| MCP Initialize | Both scripts | ✅ |
| Tools List | `test_mcp_http.py` | ✅ |
| create_memory | `test_mcp_http.py` | ✅ |
| read_memory | `test_mcp_http.py` | ✅ |
| search_memory | `test_mcp_http.py` | ✅ |
| delete_memory | `test_mcp_http.py` | ✅ |
| get_session_context | `test_mcp_http.py` | ✅ |

## CI/CD Integration (Future)

These scripts can be integrated into GitHub Actions:

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Start Qdrant
        run: docker-compose up -d qdrant
      - name: Run tests
        run: |
          ./test_local_environment.sh &
          sleep 20
          python test_mcp_http.py
```

## Best Practices

1. **Always test locally first** - Never test experimental features in production
2. **Use test persona** - Set `X-Persona: test` to avoid polluting default data
3. **Cleanup after tests** - Scripts include automatic cleanup
4. **Check logs** - Always review logs for warnings/errors
5. **Verify Qdrant** - Ensure Qdrant is healthy before starting MCP server

## See Also

- [README.md](README.md) - Project overview and setup
- [DOCKER.md](DOCKER.md) - Docker deployment guide
- `.vscode/memory-bank/techContext.md` - Debug commands reference

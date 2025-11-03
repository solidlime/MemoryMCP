#!/bin/bash

# Local Qdrant test configuration
export MEMORY_MCP_QDRANT_URL=http://127.0.0.1:6333
export MEMORY_MCP_SERVER_HOST=127.0.0.1
export MEMORY_MCP_SERVER_PORT=26262
export MEMORY_MCP_EMBEDDINGS_MODEL=cl-nagoya/ruri-v3-30m
export MEMORY_MCP_RERANKER_MODEL=hotchpotch/japanese-reranker-xsmall-v2
export MEMORY_MCP_EMBEDDINGS_DEVICE=cpu 
export MEMORY_MCP_SENTIMENT_MODEL=cardiffnlp/twitter-xlm-roberta-base-sentiment

echo "🔧 Environment variables set:"
echo "QDRANT_URL: $MEMORY_MCP_QDRANT_URL"
echo "SERVER: $MEMORY_MCP_SERVER_HOST:$MEMORY_MCP_SERVER_PORT"
echo ""

# Activate virtual environment and start server
source venv-rag/bin/activate
python3 memory_mcp.py
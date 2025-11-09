# Multi-stage build for memory-mcp with FastMCP - Optimized
# Build stage: Install dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt ./

# Install PyTorch CPU version first (to avoid CUDA dependencies)
# Use PyTorch's CPU-only index to prevent CUDA packages
RUN pip install --no-cache-dir \
    torch \
    torchvision \
    torchaudio \
    --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Runtime stage: Copy only necessary files
FROM python:3.12-slim

ENV APP_HOME=/opt/memory-mcp \
    DATA_HOME=/data \
    TZ=Asia/Tokyo

# Set working directory
WORKDIR ${APP_HOME}

# Install only runtime dependencies (curl for healthcheck, tzdata for timezone)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Clean up Python cache and unnecessary files to reduce image size
RUN find /usr/local/lib/python3.12/site-packages -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.12/site-packages -type d -name tests -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.12/site-packages -type d -name test -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.12/site-packages -type f -name '*.pyc' -delete && \
    find /usr/local/lib/python3.12/site-packages -type f -name '*.pyo' -delete && \
    find /usr/local/lib/python3.12/site-packages -type f -name '*.c' -delete && \
    find /usr/local/lib/python3.12/site-packages -type f -name '*.h' -delete && \
    rm -rf /usr/local/lib/python3.12/site-packages/pip /usr/local/lib/python3.12/site-packages/setuptools

# Copy application code
COPY . ${APP_HOME}

# Remove config.json from app directory (will be loaded from data/ at runtime)
RUN rm -f ${APP_HOME}/data/config.json 2>/dev/null || true

# Create directories for runtime data and caches
RUN mkdir -p ${DATA_HOME}/memory \
    && mkdir -p ${DATA_HOME}/logs \
    && mkdir -p ${DATA_HOME}/cache

# Default runtime environment
ENV HF_HOME=${DATA_HOME}/cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=${DATA_HOME}/cache/sentence_transformers \
    TORCH_HOME=${DATA_HOME}/cache/torch \
    MEMORY_MCP_DATA_DIR=${DATA_HOME} \
    MEMORY_MCP_CONFIG_PATH=${DATA_HOME}/config.json \
    MEMORY_MCP_SERVER_HOST=0.0.0.0 \
    MEMORY_MCP_SERVER_PORT=26262 \
    MEMORY_MCP_EMBEDDINGS_MODEL=cl-nagoya/ruri-v3-30m \
    MEMORY_MCP_EMBEDDINGS_DEVICE=cpu \
    MEMORY_MCP_RERANKER_MODEL=hotchpotch/japanese-reranker-xsmall-v2 \
    MEMORY_MCP_RERANKER_TOP_N=5 \
    MEMORY_MCP_STORAGE_BACKEND=qdrant \
    MEMORY_MCP_QDRANT_URL=http://nas:6333 \
    MEMORY_MCP_QDRANT_COLLECTION_PREFIX=memory_ \
    MEMORY_MCP_VECTOR_REBUILD_MODE=idle \
    MEMORY_MCP_VECTOR_REBUILD_IDLE_SECONDS=30 \
    MEMORY_MCP_VECTOR_REBUILD_MIN_INTERVAL=120 \
    MEMORY_MCP_AUTO_CLEANUP_ENABLED=true \
    MEMORY_MCP_AUTO_CLEANUP_IDLE_MINUTES=30 \
    MEMORY_MCP_AUTO_CLEANUP_CHECK_INTERVAL_SECONDS=300 \
    MEMORY_MCP_AUTO_CLEANUP_DUPLICATE_THRESHOLD=0.90 \
    MEMORY_MCP_AUTO_CLEANUP_MIN_SIMILARITY_TO_REPORT=0.85 \
    MEMORY_MCP_AUTO_CLEANUP_MAX_SUGGESTIONS_PER_RUN=20 \
    PYTHONUNBUFFERED=1

# Expose FastMCP HTTP port
EXPOSE 26262

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:26262/health || exit 1

# Run the MCP server
CMD ["python", "memory_mcp.py"]

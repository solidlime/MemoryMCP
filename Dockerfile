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

# Copy application code (v2: memory_mcp package only)
COPY memory_mcp/ ${APP_HOME}/memory_mcp/
COPY pyproject.toml ${APP_HOME}/

# Create directories for runtime data and caches
RUN mkdir -p ${DATA_HOME}/memory \
    ${DATA_HOME}/import \
    ${DATA_HOME}/import/done \
    ${DATA_HOME}/cache \
    ${DATA_HOME}/logs \
    ${APP_HOME}/data

# Default runtime environment — v2 Settings fields only
ENV HF_HOME=${DATA_HOME}/cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=${DATA_HOME}/cache/sentence_transformers \
    TORCH_HOME=${DATA_HOME}/cache/torch \
    MEMORY_MCP_DATA_DIR=${DATA_HOME}/memory \
    MEMORY_MCP_IMPORT_DIR=${DATA_HOME}/import \
    MEMORY_MCP_SERVER__HOST=0.0.0.0 \
    MEMORY_MCP_SERVER__PORT=26262 \
    MEMORY_MCP_EMBEDDING__MODEL=cl-nagoya/ruri-v3-30m \
    MEMORY_MCP_EMBEDDING__DEVICE=cpu \
    MEMORY_MCP_RERANKER__MODEL=hotchpotch/japanese-reranker-xsmall-v2 \
    MEMORY_MCP_RERANKER__ENABLED=true \
    MEMORY_MCP_QDRANT__URL=http://localhost:6333 \
    MEMORY_MCP_QDRANT__COLLECTION_PREFIX=memory_ \
    MEMORY_MCP_TIMEZONE=Asia/Tokyo \
    MEMORY_MCP_LOG_LEVEL=INFO \
    MEMORY_MCP_DEFAULT_PERSONA=default \
    MEMORY_MCP_CONTRADICTION_THRESHOLD=0.85 \
    MEMORY_MCP_DUPLICATE_THRESHOLD=0.90 \
    PYTHONUNBUFFERED=1

# Expose FastMCP HTTP port
EXPOSE 26262

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:26262/health || exit 1

# Run the MCP server (v2: package entrypoint)
CMD ["python", "-m", "memory_mcp.main"]

# Notes:
# - Development tip: place environment overrides in a top-level `.env` (or use Compose `env_file:`)
#   and add to `.gitignore` to avoid checking secrets into git.
# - `docker-compose.yml` has an `env_file:` line so `.env` values will be injected into the container.

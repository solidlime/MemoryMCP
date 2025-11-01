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
    pip install --no-cache-dir -r requirements.txt && \
    # Remove unnecessary packages to reduce image size
    pip uninstall -y sympy scikit-learn jedi pillow beartype 2>/dev/null || true

# Runtime stage: Copy only necessary files
FROM python:3.12-slim

ENV APP_HOME=/opt/memory-mcp \
    DATA_HOME=/data

# Set working directory
WORKDIR ${APP_HOME}

# Install only runtime dependencies (curl for healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . ${APP_HOME}

# Remove config.json to allow runtime overrides via bind mount or env vars
RUN rm -f ${APP_HOME}/config.json

# Create directories for runtime data and caches
RUN mkdir -p ${DATA_HOME}/memory \
    && mkdir -p ${DATA_HOME}/logs \
    && mkdir -p ${DATA_HOME}/cache

# Default runtime environment
ENV HF_HOME=${DATA_HOME}/cache/huggingface \
    TRANSFORMERS_CACHE=${DATA_HOME}/cache/transformers \
    SENTENCE_TRANSFORMERS_HOME=${DATA_HOME}/cache/sentence_transformers \
    TORCH_HOME=${DATA_HOME}/cache/torch \
    MEMORY_MCP_DATA_DIR=${DATA_HOME} \
    PYTHONUNBUFFERED=1

# Expose FastMCP HTTP port
EXPOSE 26262

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:26262/health || exit 1

# Run the MCP server
CMD ["python", "memory_mcp.py"]

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
    MEMORY_MCP_DATA_ROOT=/data \
    PYTHONUNBUFFERED=1 \
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
RUN mkdir -p /data

# Expose FastMCP HTTP port
EXPOSE 26262

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:26262/health || exit 1

# Run the MCP server (v2: package entrypoint)
CMD ["python", "-m", "memory_mcp.main"]

# Notes:
# - Development tip: place environment overrides in a top-level `.env` (or use Compose `env_file:`)
#   and add to `.gitignore` to avoid checking secrets into git.
# - `docker-compose.yml` has an `env_file:` line so `.env` values will be injected into the container.

# Multi-stage build for memory-mcp with FastMCP
FROM python:3.12-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY memory_mcp.py .
COPY mcp_config.json .

# Create directories for runtime data
RUN mkdir -p /app/memory /app/.cache

# Set environment variables for cache location
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/transformers
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
ENV TORCH_HOME=/app/.cache/torch

# Expose FastMCP HTTP port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the MCP server
CMD ["python", "memory_mcp.py"]

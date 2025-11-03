# Memory MCP Configuration Example

This directory contains example configuration files.

## Setup

1. Copy `config.json.example` to `../data/config.json`:
   ```bash
   cp config/config.json.example data/config.json
   ```

2. Edit `data/config.json` with your settings

3. The actual `data/config.json` is gitignored and contains your personal configuration

## Default Location

- **Example**: `config/config.json.example` (version controlled)
- **Actual**: `data/config.json` (gitignored, created at runtime)

## Environment Variables

You can override any config value using environment variables with the prefix `MEMORY_MCP_`:

```bash
export MEMORY_MCP_EMBEDDINGS_MODEL=cl-nagoya/ruri-v3-30m
export MEMORY_MCP_QDRANT_URL=http://localhost:6333
export MEMORY_MCP_SERVER_PORT=26262
```

See [README.md](../README.md) for full configuration documentation.

import asyncio
import json
import os
import sys
import uuid
import shutil
import sqlite3
import warnings
import threading
import time
import glob
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from mcp.server.fastmcp import FastMCP
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from src.utils.config_utils import (
    ensure_memory_root,
    get_config,
    get_log_file_path,
    load_config,
)
from src.utils.db_utils import db_get_entry as _db_get_entry_generic, db_recent_keys as _db_recent_keys_generic, db_count_entries as _db_count_entries_generic, db_sum_content_chars as _db_sum_content_chars_generic, clear_query_cache
from src.utils.persona_utils import (
    current_persona,
    get_current_persona,
    get_persona_dir,
    get_db_path,
    get_vector_store_path,
    get_persona_context_path,
)
from core import (
    get_current_time,
    parse_date_query,
    calculate_time_diff,
    load_persona_context,
    save_persona_context,
    load_memory_from_db,
    save_memory_to_db,
    delete_memory_from_db,
    create_memory_entry,
    generate_auto_key,
    log_operation,
)
from src.utils.vector_utils import (
    initialize_rag_sync as _initialize_rag_sync,
    add_memory_to_vector_store,
    update_memory_in_vector_store,
    delete_memory_from_vector_store,
    rebuild_vector_store,
    start_idle_rebuilder_thread,
    start_cleanup_worker_thread,
    start_auto_summarization_scheduler,
    get_vector_count,
    get_vector_metrics,
)
from src.utils.vector_utils import reranker as _reranker
from tools.vector_tools import (
    rebuild_vector_store_tool,
    migrate_sqlite_to_qdrant_tool,
    migrate_qdrant_to_sqlite_tool,
)
from tools.crud_tools import (
    create_memory,
    read_memory,
    delete_memory,
)
from tools.analysis_tools import (
    clean_memory,
    find_related_memories,
    detect_duplicates,
    merge_memories,
    analyze_sentiment,
)
from tools.search_tools import (
    search_memory,
)
from tools.knowledge_graph_tools import (
    generate_knowledge_graph,
)
from src.resources import (
    get_memory_info,
    get_memory_metrics,
    get_memory_stats,
    get_cleanup_suggestions,
)
from src.dashboard import register_http_routes

# Suppress websockets legacy deprecation warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, module='websockets.legacy')
warnings.filterwarnings('ignore', category=DeprecationWarning, module='uvicorn.protocols.websockets')
# Suppress FAISS SWIG deprecation warnings
warnings.filterwarnings('ignore', message='builtin type.*has no __module__ attribute')

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_ROOT = ensure_memory_root()

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    import io
    try:
        # Try to reconfigure stdout/stderr for emoji support
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
            sys.stderr.reconfigure(encoding='utf-8')  # type: ignore
    except (AttributeError, OSError):
        # Fallback for older Python versions or when reconfigure fails
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        except (AttributeError, OSError):
            # If all else fails, just continue with default encoding
            pass

# LangChain & RAG imports (Document only used for dummy doc snippets)
from langchain_core.documents import Document
from tqdm import tqdm

# Phase 16: Fuzzy search support
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    fuzz = None
    process = None
    RAPIDFUZZ_AVAILABLE = False

# Load configuration early for server settings
_early_config = {}
try:
    _early_config = load_config()
except Exception:
    _early_config = {}

# Initialize MCP server with configured host and port
mcp = FastMCP(
    name="memory-mcp",
    instructions="Personal memory and context management system with RAG-powered semantic search, multi-persona support, and emotional/relationship tracking",
    host=_early_config.get("server_host", "127.0.0.1"),
    port=_early_config.get("server_port", 26262)
)

# Initialize Jinja2 templates for dashboard
templates = Jinja2Templates(directory=os.path.join(SCRIPT_DIR, "templates"))

"""Persona helpers are imported from src.utils.persona_utils"""

LOG_FILE = get_log_file_path()

memory_store = {}


def _log_progress(message: str):
    """Log progress message to file (avoiding MCP protocol interference)"""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().isoformat()}] PROGRESS: {message}\n")
    except Exception:
        pass  # Silently fail if logging fails


# Global memory store (will be loaded from DB on startup)
memory_store = {}

# ---------------------------
# MCP Server initialization
# ---------------------------
# All tools imported from tools/ modules
# All resources imported from src.resources module
# Dashboard routes imported from src.dashboard module

# ========================================
# Resources and Dashboard Routes
# ========================================
# Resources imported from src.resources module
# Dashboard routes registered via dashboard.register_http_routes()

if __name__ == "__main__":
    print("🚀 MCP server starting...")
    # Load configuration (already loaded early for FastMCP initialization)
    config = load_config()
    server_host = config.get("server_host", "127.0.0.1")
    server_port = config.get("server_port", 26262)
    print(f"📝 Server configuration: {server_host}:{server_port}")
    _log_progress(f"📝 Server configuration: {server_host}:{server_port}")
    # Note: Memory database is loaded on-demand per request (no default persona loading at startup)
    # Initialize RAG synchronously before starting MCP server
    print("📥 Starting RAG system initialization...")
    try:
        _initialize_rag_sync()
        print("✅ RAG system initialized successfully")
    except Exception as e:
        print(f"⚠️  RAG system initialization failed: {e}")
        print("⚠️  Server will start anyway, but RAG features may not work")
        import traceback
        traceback.print_exc()

    # Start idle rebuild worker
    try:
        start_idle_rebuilder_thread()
        print("🧵 Idle rebuild worker started")
    except Exception as e:
        print(f"⚠️  Failed to start idle rebuild worker: {e}")

    # Phase 21: Start cleanup worker
    try:
        start_cleanup_worker_thread()
        print("🧹 Cleanup worker started")
    except Exception as e:
        print(f"⚠️  Failed to start cleanup worker: {e}")

    # Phase 38: Start auto-summarization scheduler (daily/weekly)
    try:
        start_auto_summarization_scheduler()
        print("📅 Auto-summarization scheduler started")
    except Exception as e:
        print(f"⚠️  Failed to start auto-summarization scheduler: {e}")

    # Ebbinghaus forgetting curve background decay worker
    try:
        from core.forgetting import start_ebbinghaus_worker
        start_ebbinghaus_worker()
        print("🧠 Ebbinghaus decay worker started")
    except Exception as e:
        print(f"⚠️  Failed to start Ebbinghaus worker: {e}")

    # Phase 42: Auto-migrate anniversaries on startup
    try:
        from core.memory_db import migrate_anniversaries_to_memories
        from src.utils.persona_utils import get_persona_dir
        # Get all persona directories
        memory_root = ensure_memory_root()
        if os.path.exists(memory_root):
            for persona_name in os.listdir(memory_root):
                persona_path = os.path.join(memory_root, persona_name)
                if os.path.isdir(persona_path):
                    context_path = os.path.join(persona_path, "persona_context.json")
                    if os.path.exists(context_path):
                        with open(context_path, 'r', encoding='utf-8') as f:
                            context = json.load(f)
                        if context.get("anniversaries") and len(context["anniversaries"]) > 0:
                            result = migrate_anniversaries_to_memories(persona_name)
                            if result["migrated"] > 0:
                                context["anniversaries"] = []
                                with open(context_path, 'w', encoding='utf-8') as f:
                                    json.dump(context, f, ensure_ascii=False, indent=2)
                                print(f"🎂 Migrated {result['migrated']} anniversaries for {persona_name}")
        print("✅ Anniversary migration check completed")
    except Exception as e:
        print(f"⚠️  Failed to check anniversary migration: {e}")

    # Register dashboard HTTP routes
    try:
        register_http_routes(mcp, templates)
        print("🌐 Dashboard HTTP routes registered")
    except Exception as e:
        print(f"⚠️  Failed to register dashboard routes: {e}")

    # ツール/リソースの登録（デコレータではなく動的登録）
    try:
        import tools_memory
        tools_memory.register_tools(mcp)
        tools_memory.register_resources(mcp)
        print("🧰 Tools and resources registered")
    except Exception as e:
        print(f"⚠️  Failed to register tools/resources: {e}")

    # Run MCP server with streamable-http transport
    mcp.run(transport='streamable-http')

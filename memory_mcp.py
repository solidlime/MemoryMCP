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
from config_utils import (
    ensure_memory_root,
    get_config,
    get_log_file_path,
    load_config,
)
from db_utils import db_get_entry as _db_get_entry_generic, db_recent_keys as _db_recent_keys_generic, db_count_entries as _db_count_entries_generic, db_sum_content_chars as _db_sum_content_chars_generic, clear_query_cache
from persona_utils import (
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
from vector_utils import (
    initialize_rag_sync as _initialize_rag_sync,
    add_memory_to_vector_store,
    update_memory_in_vector_store,
    delete_memory_from_vector_store,
    rebuild_vector_store,
    start_idle_rebuilder_thread,
    start_cleanup_worker_thread,
    get_vector_count,
    get_vector_metrics,
)
from vector_utils import reranker as _reranker
from tools.context_tools import get_time_since_last_conversation, get_persona_context
from tools.vector_tools import (
    rebuild_vector_store_tool,
    migrate_sqlite_to_qdrant_tool,
    migrate_qdrant_to_sqlite_tool,
)
from tools.crud_tools import (
    list_memory,
    create_memory,
    read_memory,
    update_memory,
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
    search_memory_rag,
)
from tools.knowledge_graph_tools import (
    generate_knowledge_graph,
)

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
    "Memory Service",
    host=_early_config.get("server_host", "127.0.0.1"),
    port=_early_config.get("server_port", 8000)
)

# Initialize Jinja2 templates for dashboard
templates = Jinja2Templates(directory=os.path.join(SCRIPT_DIR, "templates"))

"""Persona helpers are imported from persona_utils"""

LOG_FILE = get_log_file_path()

memory_store = {}

def _get_rebuild_config():
    cfg = load_config() or {}
    vr = cfg.get("vector_rebuild", {}) if isinstance(cfg, dict) else {}
    return {
        "mode": vr.get("mode", "idle"),
        "idle_seconds": int(vr.get("idle_seconds", 30)),
        "min_interval": int(vr.get("min_interval", 120)),
    }

"""Vector store idle rebuild handled in vector_utils"""

def _log_progress(message: str):
    """Log progress message to file (avoiding MCP protocol interference)"""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().isoformat()}] PROGRESS: {message}\n")
    except Exception:
        pass  # Silently fail if logging fails

"""Persona path helpers are imported from persona_utils"""

# ========================================
# End of Phase 12 Time-awareness Functions
# ========================================

"""Vector/RAG initialization and rebuild now handled by vector_utils"""

# Global memory store (will be loaded from DB on startup)
memory_store = {}

# ---------------------------
# DB helper utilities (refactor)
# ---------------------------
def db_get_entry(key: str):
    """Wrapper to generic helper with current persona db_path"""
    return _db_get_entry_generic(get_db_path(), key)

def db_recent_keys(limit: int = 5) -> list:
    return _db_recent_keys_generic(get_db_path(), limit)

def db_count_entries() -> int:
    return _db_count_entries_generic(get_db_path())

def db_sum_content_chars() -> int:
    return _db_sum_content_chars_generic(get_db_path())

# ---------------------------
# MCP Server initialization
# ---------------------------
# CRUD tools imported from tools/crud_tools.py
# Search tools imported from tools/search_tools.py

# ========================================
# Phase 12: Time-awareness Tools
# ========================================

# ========================================
# End of Phase 12 Time-awareness Tools
# ========================================
# Context and Vector tools imported from tools/
# Knowledge Graph tool imported from tools/knowledge_graph_tools.py

# ========================================
# Resource: Memory Info
# ========================================

def get_memory_info() -> str:
    """Provide memory service info (DB-source of truth)"""
    entries = db_count_entries()
    total_chars = db_sum_content_chars()
    vector_count = get_vector_count()
    db_path = get_db_path()
    persona = get_current_persona()
    cfg = _get_rebuild_config()
    return (
        f"User Memory System Info:\n"
        f"- Entries: {entries}\n"
        f"- Total chars: {total_chars}\n"
        f"- Vector Store: {vector_count} documents\n"
        f"- Reranker: {'Available' if _reranker else 'Not available'}\n"
        f"- Database: {db_path}\n"
        f"- Persona: {persona}\n"
        f"- Vector Rebuild: mode={cfg.get('mode')}, idle_seconds={cfg.get('idle_seconds')}, min_interval={cfg.get('min_interval')}\n"
        f"- Tools: create_memory, read_memory, update_memory, delete_memory, list_memory, search_memory, search_memory_rag, search_memory_by_date, clean_memory\n"
        f"- Key format: memory_YYYYMMDDHHMMSS\n"
        f"- Save format: 'User is ...'\n"
    )

# ========================================
# Resource: Memory Metrics
# ========================================

def get_memory_metrics() -> str:
    """
    Provide detailed metrics for monitoring and debugging.
    
    Returns:
        Formatted string with:
        - Embeddings model name and load status
        - Reranker model name and load status
        - Vector store document count
        - Dirty status (rebuild pending)
        - Last write/rebuild timestamps
        - Rebuild configuration
    """
    from datetime import datetime
    
    metrics = get_vector_metrics()
    persona = get_current_persona()
    
    # Format timestamps
    def format_ts(ts: float) -> str:
        if ts > 0:
            return datetime.fromtimestamp(ts).isoformat()
        return "Never"
    
    last_write = format_ts(metrics["last_write_ts"])
    last_rebuild = format_ts(metrics["last_rebuild_ts"])
    
    rebuild_cfg = metrics["rebuild_config"]
    
    return (
        f"📊 Memory Metrics (persona: {persona}):\n"
        f"\n"
        f"🧠 Models:\n"
        f"  - Embeddings: {metrics['embeddings_model'] or 'Not loaded'} "
        f"({'✅ Loaded' if metrics['embeddings_loaded'] else '❌ Not loaded'})\n"
        f"  - Reranker: {metrics['reranker_model'] or 'Not loaded'} "
        f"({'✅ Loaded' if metrics['reranker_loaded'] else '❌ Not loaded'})\n"
        f"\n"
        f"📦 Vector Store:\n"
        f"  - Documents: {metrics['vector_count']}\n"
        f"  - Dirty: {'✅ Yes (rebuild pending)' if metrics['dirty'] else '❌ No'}\n"
        f"\n"
        f"⏰ Timestamps:\n"
        f"  - Last Write: {last_write}\n"
        f"  - Last Rebuild: {last_rebuild}\n"
        f"\n"
        f"⚙️  Rebuild Config:\n"
        f"  - Mode: {rebuild_cfg['mode']}\n"
        f"  - Idle Seconds: {rebuild_cfg['idle_seconds']}\n"
        f"  - Min Interval: {rebuild_cfg['min_interval']}\n"
    )

# ========================================
# Resource: Memory Statistics Dashboard
# ========================================

def get_memory_stats() -> str:
    """
    Provide comprehensive memory statistics dashboard.
    
    Returns:
        Formatted string with:
        - Total memory count and date range
        - Tag distribution (with percentages)
        - Emotion distribution (with percentages)
        - Timeline (daily memory counts for last 7 days)
        - Link analysis (most mentioned [[links]])
    """
    import re
    from collections import Counter, defaultdict
    from datetime import datetime, timedelta
    
    db_path = get_db_path()
    persona = get_current_persona()
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # ========== Basic Stats ==========
            cursor.execute("SELECT COUNT(*) FROM memories")
            total_count = cursor.fetchone()[0]
            
            if total_count == 0:
                return f"📊 Memory Statistics (persona: {persona}):\n\n💡 No memories yet!"
            
            # Get date range
            cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM memories")
            min_date_str, max_date_str = cursor.fetchone()
            min_date = datetime.fromisoformat(min_date_str).date()
            max_date = datetime.fromisoformat(max_date_str).date()
            date_range_days = (max_date - min_date).days + 1
            avg_per_day = total_count / date_range_days if date_range_days > 0 else 0
            
            # ========== Tag Distribution ==========
            cursor.execute("SELECT tags FROM memories WHERE tags IS NOT NULL AND tags != ''")
            tag_counter = Counter()
            for row in cursor.fetchall():
                tags_json = row[0]
                try:
                    tags_list = json.loads(tags_json)
                    tag_counter.update(tags_list)
                except:
                    pass
            
            # ========== Emotion Distribution ==========
            # Load persona context to get emotion history
            context = load_persona_context()
            emotion_history = context.get("emotion_history", [])
            emotion_counter = Counter()
            for entry in emotion_history:
                emotion_type = entry.get("emotion_type")
                if emotion_type:
                    emotion_counter[emotion_type] += 1
            
            # ========== Timeline (last 7 days) ==========
            cursor.execute("SELECT created_at FROM memories")
            date_counter = Counter()
            for row in cursor.fetchall():
                created_at = datetime.fromisoformat(row[0]).date()
                date_counter[created_at] += 1
            
            # Get last 7 days
            today = datetime.now().date()
            timeline = []
            for i in range(6, -1, -1):
                day = today - timedelta(days=i)
                count = date_counter.get(day, 0)
                timeline.append((day, count))
            
            # ========== Link Analysis ==========
            cursor.execute("SELECT content FROM memories")
            link_counter = Counter()
            link_pattern = re.compile(r'\[\[(.+?)\]\]')
            for row in cursor.fetchall():
                content = row[0]
                matches = link_pattern.findall(content)
                link_counter.update(matches)
            
            # ========== Format Output ==========
            output = f"📊 Memory Statistics Dashboard (persona: {persona})\n"
            output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Basic stats
            output += f"📦 Total Memories: {total_count}\n"
            output += f"📅 Date Range: {min_date} ~ {max_date} ({date_range_days} days)\n"
            output += f"📈 Average per day: {avg_per_day:.2f} memories\n\n"
            
            # Tag distribution
            if tag_counter:
                output += "🏷️  Tag Distribution:\n"
                for tag, count in tag_counter.most_common(10):
                    percentage = (count / total_count) * 100
                    output += f"  - {tag}: {count} ({percentage:.1f}%)\n"
                output += "\n"
            
            # Emotion distribution
            if emotion_counter:
                output += "😊 Emotion Distribution:\n"
                total_emotions = sum(emotion_counter.values())
                for emotion, count in emotion_counter.most_common(10):
                    percentage = (count / total_emotions) * 100
                    output += f"  - {emotion}: {count} ({percentage:.1f}%)\n"
                output += "\n"
            
            # Timeline
            output += "📆 Timeline (last 7 days):\n"
            max_count = max([count for _, count in timeline]) if timeline else 1
            for day, count in timeline:
                bar_length = int((count / max_count) * 10) if max_count > 0 else 0
                bar = "█" * bar_length
                output += f"  {day}: {bar} {count}\n"
            output += "\n"
            
            # Link analysis
            if link_counter:
                output += "🔗 Link Analysis (top 10):\n"
                top_links = link_counter.most_common(10)
                output += "  Most mentioned: "
                link_strs = [f"[[{link}]]({count})" for link, count in top_links]
                output += ", ".join(link_strs)
                output += "\n"
            
            return output
            
    except Exception as e:
        return f"❌ Error generating statistics: {e}"

# ========================================
# Phase 22: Web Dashboard HTTP API
# ========================================

def _get_memory_info_data(persona: str) -> dict:
    """Core function to get memory info data for a specific persona."""
    # Temporarily override persona context
    original_persona = current_persona.get()
    current_persona.set(persona)
    
    try:
        entries = db_count_entries()
        total_chars = db_sum_content_chars()
        vector_count = get_vector_count()
        
        # Load persona context
        context = load_persona_context()
        
        # Get database created date
        db_path = get_db_path()
        if os.path.exists(db_path):
            created_at = datetime.fromtimestamp(os.path.getctime(db_path)).isoformat()
        else:
            created_at = "Unknown"
        
        # Get last conversation time
        last_conv = context.get("last_conversation_time")
        if last_conv:
            last_conversation = calculate_time_diff(last_conv)
        else:
            last_conversation = "Never"
        
        return {
            "persona": persona,
            "total_memories": entries,
            "total_chars": total_chars,
            "vector_count": vector_count,
            "created_at": created_at,
            "last_conversation": last_conversation,
            "current_emotion": context.get("current_emotion", "neutral"),
            "physical_state": context.get("physical_state", "normal"),
            "mental_state": context.get("mental_state", "calm"),
            "environment": context.get("environment", "unknown")
        }
    finally:
        current_persona.set(original_persona)

def _get_memory_metrics_data(persona: str) -> dict:
    """Core function to get memory metrics data for a specific persona."""
    original_persona = current_persona.get()
    current_persona.set(persona)
    
    try:
        import re
        from collections import Counter
        
        db_path = get_db_path()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Tag distribution
            cursor.execute("SELECT tags FROM memories WHERE tags IS NOT NULL AND tags != ''")
            tag_counter = Counter()
            for row in cursor.fetchall():
                tags_json = row[0]
                try:
                    tags_list = json.loads(tags_json)
                    tag_counter.update(tags_list)
                except:
                    pass
            
            # Emotion distribution
            context = load_persona_context()
            emotion_history = context.get("emotion_history", [])
            emotion_counter = Counter()
            for entry in emotion_history:
                emotion_type = entry.get("emotion_type")
                if emotion_type:
                    emotion_counter[emotion_type] += 1
            
            # Tagged/Linked memory counts
            cursor.execute("SELECT COUNT(*) FROM memories WHERE tags IS NOT NULL AND tags != ''")
            tagged_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT content FROM memories")
            link_pattern = re.compile(r'\[\[(.+?)\]\]')
            linked_count = 0
            for row in cursor.fetchall():
                if link_pattern.search(row[0]):
                    linked_count += 1
            
            return {
                "persona": persona,
                "top_tags": dict(tag_counter.most_common(10)),
                "emotion_distribution": dict(emotion_counter.most_common(10)),
                "tagged_memories_count": tagged_count,
                "linked_memories_count": linked_count
            }
    finally:
        current_persona.set(original_persona)

def _get_memory_stats_data(persona: str) -> dict:
    """Core function to get memory stats data for a specific persona."""
    original_persona = current_persona.get()
    current_persona.set(persona)
    
    try:
        import re
        from collections import Counter
        
        db_path = get_db_path()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Timeline (last 7 days)
            cursor.execute("SELECT created_at FROM memories")
            date_counter = Counter()
            for row in cursor.fetchall():
                created_at = datetime.fromisoformat(row[0]).date()
                date_counter[created_at] += 1
            
            today = datetime.now().date()
            timeline = []
            for i in range(6, -1, -1):
                day = today - timedelta(days=i)
                count = date_counter.get(day, 0)
                timeline.append({"date": str(day), "count": count})
            
            # Tag distribution
            cursor.execute("SELECT tags FROM memories WHERE tags IS NOT NULL AND tags != ''")
            tag_counter = Counter()
            for row in cursor.fetchall():
                tags_json = row[0]
                try:
                    tags_list = json.loads(tags_json)
                    tag_counter.update(tags_list)
                except:
                    pass
            
            # Link analysis
            cursor.execute("SELECT content FROM memories")
            link_counter = Counter()
            link_pattern = re.compile(r'\[\[(.+?)\]\]')
            for row in cursor.fetchall():
                content = row[0]
                matches = link_pattern.findall(content)
                link_counter.update(matches)
            
            return {
                "persona": persona,
                "last_7_days": timeline,
                "tag_distribution": dict(tag_counter.most_common(10)),
                "top_links": dict(link_counter.most_common(10))
            }
    finally:
        current_persona.set(original_persona)

def _get_latest_knowledge_graph(persona: str) -> str:
    """Get the URL of the latest knowledge graph HTML file for a persona."""
    pattern = os.path.join(SCRIPT_DIR, "output", f"knowledge_graph_{persona}_*.html")
    files = glob.glob(pattern)
    if not files:
        return None
    # Return the latest file (based on timestamp in filename)
    latest = max(files)
    # Return relative URL path
    filename = os.path.basename(latest)
    return f"/output/{filename}"

# HTTP Routes for Dashboard
@mcp.custom_route("/", methods=["GET"])
async def dashboard(request: Request):
    """Serve the dashboard HTML page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Simple health endpoint for Docker healthcheck
@mcp.custom_route("/health", methods=["GET"])
async def healthcheck(request: Request):
    """Return 200 OK when server is healthy."""
    try:
        persona = get_current_persona()
    except Exception:
        persona = "unknown"
    return JSONResponse({
        "status": "ok",
        "persona": persona,
        "time": datetime.now().isoformat()
    })

@mcp.custom_route("/api/personas", methods=["GET"])
async def get_personas(request: Request):
    """Get list of available personas."""
    memory_dir = MEMORY_ROOT
    if not os.path.exists(memory_dir):
        return JSONResponse([])
    
    personas = []
    for item in os.listdir(memory_dir):
        item_path = os.path.join(memory_dir, item)
        if os.path.isdir(item_path):
            # Check if it has a valid database
            db_path = os.path.join(item_path, "memory.sqlite")
            if os.path.exists(db_path):
                personas.append(item)
    
    return JSONResponse(personas)

@mcp.custom_route("/api/dashboard/{persona}", methods=["GET"])
async def get_dashboard_data(request: Request):
    """Get dashboard data for a specific persona."""
    persona = request.path_params.get("persona")
    
    # Validate persona exists
    memory_dir = os.path.join(MEMORY_ROOT, persona)
    if not os.path.exists(memory_dir):
        raise HTTPException(status_code=404, detail=f"Persona '{persona}' not found")
    
    try:
        info = _get_memory_info_data(persona)
        metrics = _get_memory_metrics_data(persona)
        stats = _get_memory_stats_data(persona)
        kg_url = _get_latest_knowledge_graph(persona)
        
        return JSONResponse({
            "persona": persona,
            "info": info,
            "metrics": metrics,
            "stats": stats,
            "knowledge_graph_url": kg_url,
            "last_updated": datetime.now().isoformat()
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading data: {str(e)}")

@mcp.custom_route("/output/{filename}", methods=["GET"])
async def serve_output_file(request: Request):
    """Serve static files from the output directory."""
    filename = request.path_params.get("filename")
    file_path = os.path.join(SCRIPT_DIR, "output", filename)
    
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=403, detail="Invalid filename")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)

# ========================================
# Resource: Cleanup Suggestions (Phase 21)
# ========================================

def get_cleanup_suggestions() -> str:
    """
    Provide cleanup suggestions generated by idle worker.
    
    Returns:
        Formatted cleanup suggestions with merge commands
    """
    try:
        persona = get_current_persona()
        persona_dir = get_persona_dir(persona)
        suggestions_file = os.path.join(persona_dir, "cleanup_suggestions.json")
        
        if not os.path.exists(suggestions_file):
            return (
                f"🧹 Cleanup Suggestions (persona: {persona})\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"No suggestions available yet.\n\n"
                f"💡 Suggestions are generated automatically after 30 minutes of idle time.\n"
                f"   You can also run: detect_duplicates(threshold=0.90)\n"
            )
        
        # Load suggestions
        with open(suggestions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Calculate time since generation
        generated_at = datetime.fromisoformat(data['generated_at'])
        now = datetime.now(generated_at.tzinfo)
        time_diff = now - generated_at
        
        if time_diff.days > 0:
            time_ago = f"{time_diff.days}日前"
        elif time_diff.seconds >= 3600:
            hours = time_diff.seconds // 3600
            time_ago = f"{hours}時間前"
        elif time_diff.seconds >= 60:
            minutes = time_diff.seconds // 60
            time_ago = f"{minutes}分前"
        else:
            time_ago = "たった今"
        
        # Format output
        output = f"🧹 Cleanup Suggestions (persona: {data['persona']})\n"
        output += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        output += f"Generated: {time_ago}\n"
        output += f"Total memories: {data['total_memories']}\n\n"
        
        summary = data['summary']
        if summary['total_groups'] == 0:
            output += "✅ No duplicate or similar memories found.\n"
            output += "   Your memory is well organized!\n"
            return output
        
        # Group by priority
        high_priority = [g for g in data['groups'] if g['priority'] == 'high']
        medium_priority = [g for g in data['groups'] if g['priority'] == 'medium']
        low_priority = [g for g in data['groups'] if g['priority'] == 'low']
        
        # High priority
        if high_priority:
            output += f"━━━ 🔴 High Priority ({len(high_priority)} groups) ━━━\n"
            output += "Almost identical - strongly recommend merging\n\n"
            for group in high_priority[:5]:  # Show top 5
                output += f"Group {group['group_id']}: {len(group['memory_keys'])} memories ({group['similarity']*100:.1f}% similar)\n"
                for key in group['memory_keys']:
                    output += f"  📝 {key}\n"
                output += f"  Preview: {group['preview']}\n"
                output += f"  💡 Run: merge_memories({json.dumps(group['memory_keys'])})\n\n"
        
        # Medium priority
        if medium_priority:
            output += f"━━━ 🟡 Medium Priority ({len(medium_priority)} groups) ━━━\n"
            output += "Very similar - consider merging\n\n"
            for group in medium_priority[:3]:  # Show top 3
                output += f"Group {group['group_id']}: {len(group['memory_keys'])} memories ({group['similarity']*100:.1f}% similar)\n"
                for key in group['memory_keys']:
                    output += f"  📝 {key}\n"
                output += f"  💡 Review: read_memory('{group['memory_keys'][0]}')\n\n"
        
        # Low priority
        if low_priority:
            output += f"━━━ 🟢 Low Priority ({len(low_priority)} groups) ━━━\n"
            output += "Somewhat similar - may be related\n"
            output += f"  {len(low_priority)} groups found (not shown for brevity)\n\n"
        
        # Summary
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        output += f"📊 Summary:\n"
        output += f"  - Total groups: {summary['total_groups']}\n"
        output += f"  - High priority: {summary['high_priority']}\n"
        output += f"  - Medium priority: {summary['medium_priority']}\n"
        output += f"  - Low priority: {summary['low_priority']}\n\n"
        output += "💡 Next cleanup check will run automatically after idle time.\n"
        
        return output
        
    except Exception as e:
        return f"❌ Error loading cleanup suggestions: {e}"

if __name__ == "__main__":
    print("🚀 MCP server starting...")
    # Load configuration (already loaded early for FastMCP initialization)
    config = load_config()
    server_host = config.get("server_host", "127.0.0.1")
    server_port = config.get("server_port", 8000)
    print(f"📝 Server configuration: {server_host}:{server_port}")
    _log_progress(f"📝 Server configuration: {server_host}:{server_port}")
    # Load memory database first (includes migration)
    print("📥 Loading memory database...")
    load_memory_from_db()
    # Initialize RAG synchronously before starting MCP server
    print("📥 Starting RAG system initialization...")
    _initialize_rag_sync()
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
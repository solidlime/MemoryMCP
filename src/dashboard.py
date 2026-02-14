"""
Dashboard and HTTP API for Memory MCP
Provides FastAPI routes for web dashboard
"""

import os
import glob
import json
import sqlite3
import re
import asyncio
from collections import Counter
from datetime import datetime, timedelta
from contextvars import ContextVar
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse

# Core imports
from core import load_persona_context, calculate_time_diff

# Utility imports
from src.utils.persona_utils import get_db_path, get_current_persona, current_persona
from src.utils.vector_utils import get_vector_count

# MCP Tools imports
from tools.unified_tools import memory as memory_tool, item as item_tool
from tools.context_tools import get_context as get_context_tool


# Get script directory for output files
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Use MEMORY_MCP_DATA_DIR if available (Docker), otherwise use local ./memory
DATA_DIR = os.getenv("MEMORY_MCP_DATA_DIR", SCRIPT_DIR)
MEMORY_ROOT = os.path.join(DATA_DIR, "memory")


def db_count_entries() -> int:
    """Count total entries in database."""
    from src.utils.db_utils import db_count_entries as db_count_impl
    return db_count_impl(get_db_path())


def db_sum_content_chars() -> int:
    """Sum total content characters in database."""
    from src.utils.db_utils import db_sum_content_chars as db_sum_impl
    return db_sum_impl(get_db_path())


def _get_current_equipment(persona: str) -> dict:
    """Get current equipment from item.sqlite database.

    Args:
        persona: Persona name

    Returns:
        Dictionary of {slot: item_name} for currently equipped items
    """
    from core.equipment_db import EquipmentDB

    db = EquipmentDB(persona)
    return db.get_equipped_items()


# ========================================
# Dashboard Data Helper Functions
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
            created_at_dt = datetime.fromtimestamp(os.path.getctime(db_path))
            # Format: "YYYY-MM-DD HH:MM:SS"
            created_at = created_at_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            created_at = "Unknown"

        # Get last conversation time (from persona_context.json)
        last_conversation_raw = context.get("last_conversation_time", "Never")

        # Remove timezone suffix (+09:00, etc.) for cleaner display
        if last_conversation_raw != "Never":
            # Format: "YYYY-MM-DDTHH:MM:SS+09:00" → "YYYY-MM-DD HH:MM:SS"
            last_conversation = last_conversation_raw[:19].replace("T", " ")
        else:
            last_conversation = last_conversation_raw

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
            "environment": context.get("environment", "unknown"),
            "relationship_status": context.get("relationship_status", "normal"),
            "current_equipment": _get_current_equipment(persona)
        }
    finally:
        current_persona.set(original_persona)


def _get_memory_metrics_data(persona: str) -> dict:
    """Core function to get memory metrics data for a specific persona."""
    original_persona = current_persona.get()
    current_persona.set(persona)

    try:
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
                except (json.JSONDecodeError, TypeError):
                    pass

            # Emotion distribution from memory emotion column
            cursor.execute("SELECT emotion FROM memories WHERE emotion IS NOT NULL AND emotion != ''")
            emotion_counter = Counter()
            for row in cursor.fetchall():
                emotion = row[0]
                if emotion:
                    emotion_counter[emotion] += 1

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
    """Core function to get memory stats data for a specific persona.
    Respects privacy settings - excludes secret/private memories from dashboard."""
    original_persona = current_persona.get()
    current_persona.set(persona)

    try:
        db_path = get_db_path()

        # Get dashboard privacy filter level and timeline config
        from src.utils.config_utils import load_config
        cfg = load_config()
        dashboard_max = cfg.get("privacy", {}).get("dashboard_max_level", "internal")
        timeline_days = cfg.get("dashboard", {}).get("timeline_days", 14)
        _PRIV_RANK = {"public": 0, "internal": 1, "private": 2, "secret": 3}
        max_rank = _PRIV_RANK.get(dashboard_max, 1)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Timeline (configurable days, default 14) - with privacy filter
            cursor.execute("SELECT created_at, privacy_level FROM memories")
            date_counter = Counter()
            for row in cursor.fetchall():
                priv = row[1] if row[1] else "internal"
                if _PRIV_RANK.get(priv, 1) <= max_rank:
                    created_at = datetime.fromisoformat(row[0]).date()
                    date_counter[created_at] += 1

            today = datetime.now().date()
            timeline = []
            for i in range(timeline_days - 1, -1, -1):
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
                except (json.JSONDecodeError, TypeError):
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
                "timeline": timeline,
                "last_7_days": timeline,  # Backward compat alias
                "timeline_days": timeline_days,
                "tag_distribution": dict(tag_counter),  # Send all tags instead of top 10
                "top_links": dict(link_counter.most_common(10))
            }
    finally:
        current_persona.set(original_persona)


def _get_latest_knowledge_graph(persona: str) -> str:
    """Get the URL of the knowledge graph HTML file for a persona."""
    # Knowledge graph is now stored in persona memory directory
    memory_dir = os.path.join(MEMORY_ROOT, persona)
    kg_path = os.path.join(memory_dir, "knowledge_graph.html")

    if not os.path.exists(kg_path):
        return None

    # Return relative URL path
    return f"/persona/{persona}/knowledge_graph.html"


# ========================================
# HTTP Routes Registration Function
# ========================================

def register_http_routes(mcp, templates):
    """
    Register HTTP routes with the MCP server.

    Args:
        mcp: FastMCP server instance
        templates: Jinja2Templates instance for rendering HTML
    """

    @mcp.custom_route("/", methods=["GET"])
    async def dashboard(request: Request):
        """Serve the dashboard HTML page."""
        return templates.TemplateResponse("dashboard.html", {"request": request})

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
        if not os.path.exists(MEMORY_ROOT):
            return JSONResponse([])

        personas = []
        for item in os.listdir(MEMORY_ROOT):
            item_path = os.path.join(MEMORY_ROOT, item)
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

    @mcp.custom_route("/persona/{persona}/knowledge_graph.html", methods=["GET"])
    async def serve_knowledge_graph(request: Request):
        """Serve knowledge graph HTML file from persona memory directory."""
        persona = request.path_params.get("persona")

        # Security: prevent directory traversal
        if ".." in persona or "/" in persona or "\\" in persona:
            raise HTTPException(status_code=403, detail="Invalid persona name")

        file_path = os.path.join(MEMORY_ROOT, persona, "knowledge_graph.html")

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Knowledge graph not found")

        return FileResponse(file_path)

    @mcp.custom_route("/api/knowledge-graph-status/{persona}", methods=["GET"])
    async def knowledge_graph_status(request: Request):
        """Get knowledge graph file status (existence, age, etc.)."""
        persona = request.path_params.get("persona")

        # Security: prevent directory traversal
        if ".." in persona or "/" in persona or "\\" in persona:
            return JSONResponse({
                "success": False,
                "error": "Invalid persona name"
            }, status_code=403)

        file_path = os.path.join(MEMORY_ROOT, persona, "knowledge_graph.html")

        if not os.path.exists(file_path):
            return JSONResponse({
                "success": True,
                "exists": False,
                "url": None,
                "last_modified": None,
                "age_hours": None,
                "should_regenerate": True
            })

        # Get file modification time
        mtime = os.path.getmtime(file_path)
        last_modified = datetime.fromtimestamp(mtime).isoformat()
        age_hours = (datetime.now() - datetime.fromtimestamp(mtime)).total_seconds() / 3600

        # Auto-regenerate if older than 24 hours
        should_regenerate = age_hours > 24

        return JSONResponse({
            "success": True,
            "exists": True,
            "url": f"/persona/{persona}/knowledge_graph.html",
            "last_modified": last_modified,
            "age_hours": round(age_hours, 2),
            "should_regenerate": should_regenerate
        })

    # ========================================
    # MCP Tools API Routes (for GitHub Copilot Skills)
    # ========================================

    @mcp.custom_route("/mcp/v1/tools/memory", methods=["POST"])
    async def api_memory_tool_endpoint(request: Request):
        """
        Simplified REST API for memory tool.
        GitHub Copilot Skills can call this directly without JSON-RPC overhead.

        POST /mcp/v1/tools/memory
        {
          "operation": "create|read|search|update|delete|stats|...",
          "content": "...",
          "query": "...",
          ...other parameters...
        }
        """
        try:
            # Get persona from Authorization header (Bearer token)
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                persona = auth_header[7:]
                current_persona.set(persona)

            # Parse request body
            data = await request.json()

            # Call the memory tool with all parameters
            result = await memory_tool(**data)

            return JSONResponse(
                {"success": True, "result": result},
                media_type="application/json; charset=utf-8"
            )
        except Exception as e:
            return JSONResponse(
                {"success": False, "error": str(e)},
                status_code=400,
                media_type="application/json; charset=utf-8"
            )

    @mcp.custom_route("/mcp/v1/tools/item", methods=["POST", "GET"])
    async def api_item_tool_endpoint(request: Request):
        """
        Simplified REST API for item tool.

        POST /mcp/v1/tools/item
        {
          "operation": "add|remove|equip|unequip|search|...",
          "item_name": "...",
          ...other parameters...
        }

        GET /mcp/v1/tools/item?operation=search
        """
        try:
            # Get persona from Authorization header
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                persona = auth_header[7:]
                current_persona.set(persona)

            # Parse parameters
            if request.method == "POST":
                data = await request.json()
            else:  # GET
                data = dict(request.query_params)

            # Call the item tool
            result = await item_tool(**data)

            return JSONResponse(
                {"success": True, "result": result},
                media_type="application/json; charset=utf-8"
            )
        except Exception as e:
            return JSONResponse(
                {"success": False, "error": str(e)},
                status_code=400,
                media_type="application/json; charset=utf-8"
            )

    @mcp.custom_route("/mcp/v1/tools/get_context", methods=["POST", "GET"])
    async def api_get_context_tool_endpoint(request: Request):
        """
        Simplified REST API for get_context tool.

        POST /mcp/v1/tools/get_context
        GET /mcp/v1/tools/get_context
        """
        try:
            # Get persona from Authorization header
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                persona = auth_header[7:]
                current_persona.set(persona)

            # Call the get_context tool
            result = await get_context_tool()

            return JSONResponse(
                {"success": True, "result": result},
                media_type="application/json; charset=utf-8"
            )
        except Exception as e:
            return JSONResponse(
                {"success": False, "error": str(e)},
                status_code=400,
                media_type="application/json; charset=utf-8"
            )

    # ========================================
    # Admin Tools API Routes
    # ========================================

    @mcp.custom_route("/api/admin/clean", methods=["POST"])
    async def admin_clean_memory(request: Request):
        """Clean memory by removing duplicate lines."""
        try:
            data = await request.json()
            persona = data.get("persona")
            memory_key = data.get("key")

            if not persona or not memory_key:
                raise HTTPException(status_code=400, detail="persona and key are required")

            original_persona = current_persona.get()
            current_persona.set(persona)

            try:
                from src.utils.db_utils import clean_memory_duplicates
                clean_memory_duplicates(memory_key)
                return JSONResponse({
                    "success": True,
                    "message": f"Successfully cleaned memory {memory_key}"
                })
            finally:
                current_persona.set(original_persona)

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)

    @mcp.custom_route("/api/admin/rebuild", methods=["POST"])
    async def admin_rebuild_vector_store(request: Request):
        """Rebuild Qdrant collection from SQLite database (async background task)."""
        try:
            data = await request.json()
            persona = data.get("persona")

            if not persona:
                raise HTTPException(status_code=400, detail="persona is required")

            # Run in thread pool to avoid blocking
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            def _rebuild():
                original_persona = current_persona.get()
                current_persona.set(persona)
                try:
                    from src.utils.vector_utils import rebuild_vector_store
                    rebuild_vector_store()
                finally:
                    current_persona.set(original_persona)

            # Start async task
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(executor, _rebuild)

            return JSONResponse({
                "success": True,
                "message": f"Successfully rebuilt Qdrant collection for {persona}"
            })

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)

    @mcp.custom_route("/api/admin/migrate", methods=["POST"])
    async def admin_migrate_backend(request: Request):
        """Migrate memories between SQLite and Qdrant."""
        try:
            data = await request.json()
            persona = data.get("persona")
            source = data.get("source")  # "sqlite" or "qdrant"
            target = data.get("target")  # "sqlite" or "qdrant"

            if not all([persona, source, target]):
                raise HTTPException(status_code=400, detail="persona, source, and target are required")

            if source == target:
                raise HTTPException(status_code=400, detail="source and target must be different")

            original_persona = current_persona.get()
            current_persona.set(persona)

            try:
                if source == "sqlite" and target == "qdrant":
                    from tools.vector_tools import migrate_sqlite_to_qdrant_tool
                    result = await migrate_sqlite_to_qdrant_tool()
                    # Extract count from result message (e.g., "✅ Migrated 174 memories...")
                    import re
                    match = re.search(r'Migrated (\d+) memories', result)
                    count = int(match.group(1)) if match else 0
                    message = f"Migrated {count} memories from SQLite to Qdrant"
                elif source == "qdrant" and target == "sqlite":
                    from tools.vector_tools import migrate_qdrant_to_sqlite_tool
                    result = await migrate_qdrant_to_sqlite_tool()
                    # Extract count from result message
                    import re
                    match = re.search(r'Migrated (\d+) memories', result)
                    count = int(match.group(1)) if match else 0
                    message = f"Migrated {count} memories from Qdrant to SQLite"
                else:
                    raise HTTPException(status_code=400, detail="Invalid source/target combination")

                return JSONResponse({
                    "success": True,
                    "message": message,
                    "count": count
                })
            finally:
                current_persona.set(original_persona)

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)

    @mcp.custom_route("/api/admin/migrate-schema", methods=["POST"])
    async def admin_migrate_schema(request: Request):
        """Migrate SQLite schema to add missing columns."""
        try:
            data = await request.json()
            persona = data.get("persona")  # Optional - if None, migrate all

            # Run in thread pool to avoid blocking
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            def _migrate():
                if persona:
                    original_persona = current_persona.get()
                    current_persona.set(persona)
                try:
                    from scripts.migrate_schema import migrate_database, migrate_all_personas
                    import os

                    if persona:
                        db_path = os.path.join(MEMORY_ROOT, persona, "memory.sqlite")
                        if not os.path.exists(db_path):
                            return {"success": False, "error": f"Database not found: {db_path}"}
                        migrate_database(db_path)
                        return {"success": True, "message": f"Schema migrated for persona: {persona}"}
                    else:
                        migrate_all_personas()
                        return {"success": True, "message": "Schema migrated for all personas"}
                finally:
                    if persona:
                        current_persona.set(original_persona)

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, _migrate)

            return JSONResponse(result)
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)

    @mcp.custom_route("/api/admin/detect-duplicates", methods=["POST"])
    async def admin_detect_duplicates(request: Request):
        """Detect duplicate or similar memories (async background task)."""
        try:
            data = await request.json()
            persona = data.get("persona")
            threshold = data.get("threshold", 0.85)
            max_pairs = data.get("max_pairs", 50)

            if not persona:
                raise HTTPException(status_code=400, detail="persona is required")

            # Run in thread pool to avoid blocking
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            def _detect():
                original_persona = current_persona.get()
                current_persona.set(persona)
                try:
                    from src.utils.analysis_utils import detect_duplicate_memories
                    return detect_duplicate_memories(threshold=threshold, max_pairs=max_pairs)
                finally:
                    current_persona.set(original_persona)

            # Start async task
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                duplicates = await loop.run_in_executor(executor, _detect)

            return JSONResponse({
                "success": True,
                "duplicates": duplicates
            })

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)

    @mcp.custom_route("/api/admin/merge", methods=["POST"])
    async def admin_merge_memories(request: Request):
        """Merge multiple memories into one."""
        try:
            data = await request.json()
            persona = data.get("persona")
            memory_keys = data.get("keys", [])
            merged_content = data.get("content")
            keep_all_tags = data.get("keep_all_tags", True)
            delete_originals = data.get("delete_originals", True)

            if not persona or not memory_keys or len(memory_keys) < 2:
                raise HTTPException(status_code=400, detail="persona and at least 2 keys are required")

            original_persona = current_persona.get()
            current_persona.set(persona)

            try:
                from src.utils.analysis_utils import merge_memories
                new_key = merge_memories(
                    memory_keys=memory_keys,
                    merged_content=merged_content,
                    keep_all_tags=keep_all_tags,
                    delete_originals=delete_originals
                )
                return JSONResponse({
                    "success": True,
                    "message": f"Successfully merged {len(memory_keys)} memories",
                    "new_key": new_key
                })
            finally:
                current_persona.set(original_persona)

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)

    @mcp.custom_route("/api/admin/generate-graph", methods=["POST"])
    async def admin_generate_knowledge_graph(request: Request):
        """Generate knowledge graph visualization (async background task)."""
        try:
            data = await request.json()
            persona = data.get("persona")
            output_format = data.get("format", "html")
            min_count = data.get("min_count", 2)
            min_cooccurrence = data.get("min_cooccurrence", 1)
            remove_isolated = data.get("remove_isolated", True)

            if not persona:
                raise HTTPException(status_code=400, detail="persona is required")

            # Run in thread pool to avoid blocking
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            def _generate():
                original_persona = current_persona.get()
                current_persona.set(persona)
                try:
                    from src.utils.analysis_utils import build_knowledge_graph, export_graph_html, export_graph_json
                    from src.utils.persona_utils import get_db_path

                    graph = build_knowledge_graph(
                        min_count=min_count,
                        min_cooccurrence=min_cooccurrence,
                        remove_isolated=remove_isolated
                    )

                    if output_format == "html":
                        # Get persona memory directory
                        db_path = get_db_path()
                        persona_dir = os.path.dirname(db_path)

                        # HTML file path (single file per persona)
                        output_path = os.path.join(persona_dir, f"knowledge_graph.html")

                        # Remove old graph file if exists
                        if os.path.exists(output_path):
                            os.remove(output_path)

                        export_graph_html(graph, output_path)
                        return {
                            "success": True,
                            "message": f"Knowledge graph generated successfully",
                            "url": f"/persona/{persona}/knowledge_graph.html"
                        }
                    else:  # json
                        graph_json = export_graph_json(graph)
                        return {
                            "success": True,
                            "message": "Knowledge graph generated successfully",
                            "graph": graph_json
                        }
                finally:
                    current_persona.set(original_persona)

            # Start async task
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, _generate)

            return JSONResponse(result)

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)

    @mcp.custom_route("/api/admin/summarize", methods=["POST"])
    async def create_summary(request: Request):
        """
        Create memory summary for a specific persona and time period.
        """
        try:
            data = await request.json()
            persona = data.get("persona")
            period = data.get("period", "week")  # "day" or "week"

            if not persona:
                return JSONResponse({
                    "success": False,
                    "error": "Persona is required"
                }, status_code=400)

            # Validate persona exists
            memory_dir = os.path.join(MEMORY_ROOT, persona)
            if not os.path.exists(memory_dir):
                return JSONResponse({
                    "success": False,
                    "error": f"Persona '{persona}' not found"
                }, status_code=404)

            # Set persona context and run summarization in thread pool
            from concurrent.futures import ThreadPoolExecutor

            def _summarize():
                original_persona = current_persona.get()
                current_persona.set(persona)

                try:
                    from tools.summarization_tools import summarize_last_week, summarize_last_day

                    if period == "day":
                        result = summarize_last_day(persona=persona)
                    else:
                        result = summarize_last_week(persona=persona)

                    if result:
                        # Extract summary key from result message
                        summary_key = None
                        if "Summary node: " in result:
                            try:
                                summary_key = result.split("Summary node: ")[1].split("\n")[0].strip()
                            except (IndexError, AttributeError):
                                pass

                        return {
                            "success": True,
                            "message": result,
                            "summary_key": summary_key,
                            "period": period
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Failed to generate summary (no memories found or LLM error)"
                        }
                finally:
                    current_persona.set(original_persona)

            # Start async task
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, _summarize)

            return JSONResponse(result)

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)

    @mcp.custom_route("/api/admin/rebuild-stream", methods=["POST"])
    async def rebuild_vector_store_stream(request: Request):
        """
        Rebuild vector store with real-time progress updates via SSE.
        """
        try:
            data = await request.json()
            persona = data.get("persona")

            if not persona:
                return JSONResponse({
                    "success": False,
                    "error": "Persona is required"
                }, status_code=400)

            async def event_stream():
                try:
                    original_persona = current_persona.get()
                    current_persona.set(persona)

                    # Send start event
                    yield f"data: {json.dumps({'status': 'started', 'percent': 0, 'message': 'Starting vector store rebuild...'})}\n\n"
                    await asyncio.sleep(0.1)

                    # Simulate progress (in reality, rebuild_vector_store doesn't provide progress)
                    # We'll just show a progress animation
                    from src.utils.vector_utils import rebuild_vector_store

                    # Progress simulation
                    for i in range(10, 90, 10):
                        yield f"data: {json.dumps({'status': 'progress', 'percent': i, 'message': f'Rebuilding vectors... {i}%'})}\n\n"
                        await asyncio.sleep(0.3)

                    # Execute rebuild in thread pool
                    loop = asyncio.get_event_loop()
                    from concurrent.futures import ThreadPoolExecutor
                    with ThreadPoolExecutor() as executor:
                        def _rebuild():
                            return rebuild_vector_store()

                        result = await loop.run_in_executor(executor, _rebuild)

                    # Send completion
                    yield f"data: {json.dumps({'status': 'completed', 'percent': 100, 'message': f'Rebuild completed: {result}'})}\n\n"

                    current_persona.set(original_persona)

                except Exception as e:
                    yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)

    @mcp.custom_route("/api/admin/summarize-stream", methods=["POST"])
    async def create_summary_stream(request: Request):
        """
        Create summary with real-time progress updates via SSE.
        """
        try:
            data = await request.json()
            persona = data.get("persona")
            period = data.get("period", "week")

            if not persona:
                return JSONResponse({
                    "success": False,
                    "error": "Persona is required"
                }, status_code=400)

            async def event_stream():
                try:
                    original_persona = current_persona.get()
                    current_persona.set(persona)

                    # Send start event
                    yield f"data: {json.dumps({'status': 'started', 'percent': 0, 'message': 'Loading memories...'})}\n\n"
                    await asyncio.sleep(0.1)

                    yield f"data: {json.dumps({'status': 'progress', 'percent': 30, 'message': 'Analyzing memories...'})}\n\n"
                    await asyncio.sleep(0.3)

                    # Check if LLM is enabled
                    from src.utils.config_utils import load_config
                    config = load_config()
                    use_llm = config.get("summarization", {}).get("use_llm", False)

                    message = 'Generating summary with LLM...' if use_llm else 'Generating summary...'
                    yield f"data: {json.dumps({'status': 'progress', 'percent': 60, 'message': message})}\n\n"
                    await asyncio.sleep(0.3)

                    # Execute summarization in thread pool
                    loop = asyncio.get_event_loop()
                    from concurrent.futures import ThreadPoolExecutor
                    with ThreadPoolExecutor() as executor:
                        def _summarize():
                            from tools.summarization_tools import summarize_last_week, summarize_last_day

                            if period == "day":
                                summary_key = summarize_last_day(persona=persona)
                            else:
                                summary_key = summarize_last_week(persona=persona)

                            # Return success message
                            if summary_key:
                                period_name = "last day" if period == "day" else "last week"
                                return f"✅ Summary created successfully for {period_name}\nSummary node: {summary_key}"
                            else:
                                return None

                        result = await loop.run_in_executor(executor, _summarize)

                    if result:
                        summary_key = None
                        if "Summary node: " in result:
                            try:
                                summary_key = result.split("Summary node: ")[1].split("\n")[0].strip()
                            except (IndexError, AttributeError):
                                pass

                        yield f"data: {json.dumps({'status': 'completed', 'percent': 100, 'message': result, 'summary_key': summary_key})}\n\n"
                    else:
                        yield f"data: {json.dumps({'status': 'error', 'message': 'Failed to generate summary (no memories found in the selected period)'})}\n\n"

                    current_persona.set(original_persona)

                except Exception as e:
                    yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)

    @mcp.custom_route("/api/emotion-timeline/{persona}", methods=["GET"])
    async def emotion_timeline(request: Request):
        """
        Get emotion timeline data for visualization.
        Returns daily and weekly emotion distribution from emotion_history table (Phase 40).
        Falls back to memories table for backward compatibility.
        """
        try:
            persona = request.path_params.get("persona")
            # Validate persona exists
            memory_dir = os.path.join(MEMORY_ROOT, persona)
            if not os.path.exists(memory_dir):
                return JSONResponse({
                    "success": False,
                    "error": f"Persona '{persona}' not found"
                }, status_code=404)

            # Set persona context
            original_persona = current_persona.get()
            current_persona.set(persona)

            try:
                db_path = get_db_path()

                # Get emotion data from emotion_history table (Phase 40)
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()

                    # Check if emotion_history table exists
                    cursor.execute("""
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='emotion_history'
                    """)
                    has_history_table = cursor.fetchone() is not None

                    if has_history_table:
                        cursor.execute("PRAGMA table_info(emotion_history)")
                        history_columns = {row[1] for row in cursor.fetchall()}
                        if "emotion" in history_columns:
                            emotion_col = "emotion"
                        elif "emotion_type" in history_columns:
                            emotion_col = "emotion_type"
                        else:
                            emotion_col = None

                    if has_history_table and emotion_col:
                        # Use emotion_history table (Phase 40)
                        cursor.execute(f'''
                            SELECT
                                DATE(timestamp) as date,
                                {emotion_col} as emotion,
                                COUNT(*) as count
                            FROM emotion_history
                            WHERE {emotion_col} IS NOT NULL AND {emotion_col} != 'neutral'
                            GROUP BY DATE(timestamp), {emotion_col}
                            ORDER BY DATE(timestamp)
                        ''')

                        daily_data = {}
                        emotion_types = set()

                        for row in cursor.fetchall():
                            date_str, emotion, count = row
                            if date_str not in daily_data:
                                daily_data[date_str] = {}
                            daily_data[date_str][emotion] = count
                            emotion_types.add(emotion)

                        # Get weekly aggregation from emotion_history
                        cursor.execute(f'''
                            SELECT
                                strftime('%Y-W%W', timestamp) as week,
                                {emotion_col} as emotion,
                                COUNT(*) as count
                            FROM emotion_history
                            WHERE {emotion_col} IS NOT NULL AND {emotion_col} != 'neutral'
                            GROUP BY strftime('%Y-W%W', timestamp), {emotion_col}
                            ORDER BY strftime('%Y-W%W', timestamp)
                        ''')

                        weekly_data = {}

                        for row in cursor.fetchall():
                            week_str, emotion, count = row
                            if week_str not in weekly_data:
                                weekly_data[week_str] = {}
                            weekly_data[week_str][emotion] = count
                    else:
                        # Fallback to memories table (backward compatibility)
                        cursor.execute("PRAGMA table_info(memories)")
                        memory_columns = {row[1] for row in cursor.fetchall()}
                        if "emotion" not in memory_columns:
                            return JSONResponse({
                                "success": True,
                                "daily": [],
                                "weekly": [],
                                "emotion_types": []
                            })
                        cursor.execute('''
                            SELECT
                                DATE(created_at) as date,
                                emotion,
                                COUNT(*) as count
                            FROM memories
                            WHERE emotion IS NOT NULL AND emotion != 'neutral'
                            GROUP BY DATE(created_at), emotion
                            ORDER BY DATE(created_at)
                        ''')

                        daily_data = {}
                        emotion_types = set()

                        for row in cursor.fetchall():
                            date_str, emotion, count = row
                            if date_str not in daily_data:
                                daily_data[date_str] = {}
                            daily_data[date_str][emotion] = count
                            emotion_types.add(emotion)

                        # Get weekly aggregation from memories
                        cursor.execute('''
                            SELECT
                                strftime('%Y-W%W', created_at) as week,
                                emotion,
                                COUNT(*) as count
                            FROM memories
                            WHERE emotion IS NOT NULL AND emotion != 'neutral'
                            GROUP BY strftime('%Y-W%W', created_at), emotion
                            ORDER BY strftime('%Y-W%W', created_at)
                        ''')

                        weekly_data = {}

                        for row in cursor.fetchall():
                            week_str, emotion, count = row
                            if week_str not in weekly_data:
                                weekly_data[week_str] = {}
                            weekly_data[week_str][emotion] = count

                # Format for Chart.js
                daily_timeline = []
                for date_str, emotions in sorted(daily_data.items()):
                    daily_timeline.append({
                        "date": date_str,
                        **{emotion: emotions.get(emotion, 0) for emotion in emotion_types}
                    })

                weekly_timeline = []
                for week_str, emotions in sorted(weekly_data.items()):
                    weekly_timeline.append({
                        "week": week_str,
                        **{emotion: emotions.get(emotion, 0) for emotion in emotion_types}
                    })

                return JSONResponse({
                    "success": True,
                    "daily": daily_timeline,
                    "weekly": weekly_timeline,
                    "emotion_types": sorted(list(emotion_types))
                })

            finally:
                current_persona.set(original_persona)

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)

    @mcp.custom_route("/api/physical-sensations-timeline/{persona}", methods=["GET"])
    async def physical_sensations_timeline(request: Request):
        """
        Get physical sensations timeline data for visualization.
        Returns time-series data for fatigue, warmth, arousal, touch_response, and heart_rate_metaphor.
        """
        try:
            persona = request.path_params.get("persona")
            # Validate persona exists
            memory_dir = os.path.join(MEMORY_ROOT, persona)
            if not os.path.exists(memory_dir):
                return JSONResponse({
                    "success": False,
                    "error": f"Persona '{persona}' not found"
                }, status_code=404)

            # Set persona context
            original_persona = current_persona.get()
            current_persona.set(persona)

            try:
                # Import Phase 40 timeline function
                from core.memory_db import get_physical_sensations_timeline

                # Get 7 days of physical sensations data
                timeline_data = get_physical_sensations_timeline(days=7, persona=persona)

                if not timeline_data:
                    # Return empty data with proper structure
                    return JSONResponse({
                        "success": True,
                        "timeline": [],
                        "metrics": ["fatigue", "warmth", "arousal", "touch_response", "heart_rate_metaphor"]
                    })

                # Format timeline data for Chart.js
                formatted_timeline = []
                for entry in timeline_data:
                    formatted_timeline.append({
                        "timestamp": entry["timestamp"],
                        "fatigue": entry.get("fatigue"),
                        "warmth": entry.get("warmth"),
                        "arousal": entry.get("arousal"),
                        "touch_response": entry.get("touch_response"),
                        "heart_rate_metaphor": entry.get("heart_rate_metaphor"),
                        "memory_key": entry.get("memory_key")
                    })

                return JSONResponse({
                    "success": True,
                    "timeline": formatted_timeline,
                    "metrics": ["fatigue", "warmth", "arousal", "touch_response", "heart_rate_metaphor"]
                })

            finally:
                current_persona.set(original_persona)

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)


    @mcp.custom_route("/api/anniversaries/{persona}", methods=["GET"])
    async def anniversaries(request: Request):
        """
        Get anniversaries (important memories grouped by month-day).
        Returns list of anniversary dates with associated memories.
        """
        try:
            persona = request.path_params.get("persona")
            # Validate persona exists
            memory_dir = os.path.join(MEMORY_ROOT, persona)
            if not os.path.exists(memory_dir):
                return JSONResponse({
                    "success": False,
                    "error": f"Persona '{persona}' not found"
                }, status_code=404)

            # Set persona context
            original_persona = current_persona.get()
            current_persona.set(persona)

            try:
                from core.memory_db import get_anniversaries

                anniversaries_data = get_anniversaries(persona=persona)

                return JSONResponse({
                    "success": True,
                    "anniversaries": anniversaries_data
                })

            finally:
                current_persona.set(original_persona)

        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)


    # ─── Observation Stream / Memory Browsing APIs ───────────────────

    @mcp.custom_route("/api/observations/{persona}", methods=["GET"])
    async def observations(request: Request):
        """
        Paginated observation stream – browse all memories chronologically.
        Query params:
            page (int): page number (1-based, default 1)
            per_page (int): items per page (default 20, max 100)
            sort (str): 'desc' (newest first, default) or 'asc'
            tag (str): optional tag filter
            q (str): optional keyword filter on content
        """
        try:
            persona = request.path_params.get("persona")
            memory_dir = os.path.join(MEMORY_ROOT, persona)
            if not os.path.exists(memory_dir):
                return JSONResponse({"success": False, "error": f"Persona '{persona}' not found"}, status_code=404)

            page = max(1, int(request.query_params.get("page", 1)))
            per_page = min(100, max(1, int(request.query_params.get("per_page", 20))))
            sort_order = "ASC" if request.query_params.get("sort", "desc").lower() == "asc" else "DESC"
            tag_filter = request.query_params.get("tag", "").strip()
            q_filter = request.query_params.get("q", "").strip()

            original_persona = current_persona.get()
            current_persona.set(persona)
            try:
                db_path = get_db_path()
                # Privacy filter
                from src.utils.config_utils import load_config
                cfg = load_config()
                dashboard_max = cfg.get("privacy", {}).get("dashboard_max_level", "internal")
                _PRIV_RANK = {"public": 0, "internal": 1, "private": 2, "secret": 3}
                max_rank = _PRIV_RANK.get(dashboard_max, 1)
                allowed_levels = [lvl for lvl, rank in _PRIV_RANK.items() if rank <= max_rank]

                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='operations'")
                    if cursor.fetchone() is None:
                        return JSONResponse({
                            "success": True,
                            "total": 0,
                            "page": page,
                            "per_page": per_page,
                            "total_pages": 1,
                            "operation_breakdown": {},
                            "items": [],
                        })
                    cursor.execute("PRAGMA table_info(memories)")
                    memory_columns = {row[1] for row in cursor.fetchall()}

                    cursor.execute("PRAGMA table_info(memories)")
                    memory_columns = {row[1] for row in cursor.fetchall()}

                    # Build WHERE clause
                    if "privacy_level" in memory_columns:
                        conditions = [f"COALESCE(privacy_level, 'internal') IN ({','.join('?' for _ in allowed_levels)})"]
                        params: list = list(allowed_levels)
                    else:
                        conditions = ["1=1"]
                        params = []

                    if tag_filter:
                        conditions.append("tags LIKE ?")
                        params.append(f'%"{tag_filter}"%')
                    if q_filter:
                        conditions.append("content LIKE ?")
                        params.append(f"%{q_filter}%")

                    where = " AND ".join(conditions)

                    # Count
                    cursor.execute(f"SELECT COUNT(*) FROM memories WHERE {where}", params)
                    total = cursor.fetchone()[0]

                    # Fetch page
                    offset = (page - 1) * per_page
                    emotion_select = "emotion AS emotion_type" if "emotion" in memory_columns else "NULL AS emotion_type"
                    intensity_select = "emotion_intensity" if "emotion_intensity" in memory_columns else "NULL AS emotion_intensity"
                    select_fields = [
                        "key",
                        "content",
                        emotion_select,
                        intensity_select,
                        "importance",
                        "tags",
                        "created_at",
                        "updated_at",
                        "action_tag",
                        "environment",
                    ]
                    if "context_tags" in memory_columns:
                        select_fields.append("context_tags")
                    if "privacy_level" in memory_columns:
                        select_fields.append("privacy_level")

                    cursor.execute(
                        f"""SELECT {', '.join(select_fields)}
                            FROM memories WHERE {where}
                            ORDER BY created_at {sort_order}
                            LIMIT ? OFFSET ?""",
                        params + [per_page, offset],
                    )

                    items = []
                    for row in cursor.fetchall():
                        item = dict(row)
                        # Truncate long content for listing
                        if item.get("content") and len(item["content"]) > 300:
                            item["content_preview"] = item["content"][:300] + "..."
                            del item["content"]
                        else:
                            item["content_preview"] = item.get("content", "")
                            if "content" in item:
                                del item["content"]
                        # Parse JSON fields
                        for jf in ("tags", "context_tags"):
                            if item.get(jf):
                                try:
                                    item[jf] = json.loads(item[jf])
                                except (json.JSONDecodeError, TypeError):
                                    pass
                        items.append(item)

                    return JSONResponse({
                        "success": True,
                        "total": total,
                        "page": page,
                        "per_page": per_page,
                        "total_pages": max(1, -(-total // per_page)),
                        "items": items,
                    })
            finally:
                current_persona.set(original_persona)
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)


    @mcp.custom_route("/api/memory/{persona}/{key:path}", methods=["GET"])
    async def get_memory_by_key(request: Request):
        """
        Get a single memory by its key, with full detail + related memories.
        """
        try:
            persona = request.path_params.get("persona")
            key = request.path_params.get("key")
            memory_dir = os.path.join(MEMORY_ROOT, persona)
            if not os.path.exists(memory_dir):
                return JSONResponse({"success": False, "error": f"Persona '{persona}' not found"}, status_code=404)

            original_persona = current_persona.get()
            current_persona.set(persona)
            try:
                db_path = get_db_path()
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM memories WHERE key = ?", (key,))
                    row = cursor.fetchone()
                    if not row:
                        return JSONResponse({"success": False, "error": f"Memory '{key}' not found"}, status_code=404)

                    memory = dict(row)
                    if "emotion" in memory and "emotion_type" not in memory:
                        memory["emotion_type"] = memory.get("emotion")
                    # Parse JSON fields
                    for jf in ("tags", "context_tags"):
                        if memory.get(jf):
                            try:
                                memory[jf] = json.loads(memory[jf])
                            except (json.JSONDecodeError, TypeError):
                                pass

                    # Find related via [[links]]
                    link_pattern = re.compile(r'\[\[(.+?)\]\]')
                    linked_keys = link_pattern.findall(memory.get("content", ""))

                    # Get operation history for this key
                    cursor.execute(
                        "SELECT timestamp, operation, success, error FROM operations WHERE key = ? ORDER BY timestamp DESC LIMIT 20",
                        (key,),
                    )
                    history = [dict(r) for r in cursor.fetchall()]

                    return JSONResponse({
                        "success": True,
                        "memory": memory,
                        "linked_keys": linked_keys,
                        "history": history,
                    })
            finally:
                current_persona.set(original_persona)
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)


    # ─── Audit Log API ───────────────────────────────────────────────

    @mcp.custom_route("/api/audit-log/{persona}", methods=["GET"])
    async def audit_log(request: Request):
        """
        Browse the operations audit log with filtering and pagination.
        Query params:
            page (int): page number (1-based, default 1)
            per_page (int): items per page (default 50, max 200)
            operation (str): filter by operation type (create/read/update/delete/search etc.)
            key (str): filter by memory key
            success (str): 'true' or 'false'
            since (str): ISO date string (e.g. 2025-01-01)
        """
        try:
            persona = request.path_params.get("persona")
            memory_dir = os.path.join(MEMORY_ROOT, persona)
            if not os.path.exists(memory_dir):
                return JSONResponse({"success": False, "error": f"Persona '{persona}' not found"}, status_code=404)

            page = max(1, int(request.query_params.get("page", 1)))
            per_page = min(200, max(1, int(request.query_params.get("per_page", 50))))
            op_filter = request.query_params.get("operation", "").strip()
            key_filter = request.query_params.get("key", "").strip()
            success_filter = request.query_params.get("success", "").strip()
            since_filter = request.query_params.get("since", "").strip()

            original_persona = current_persona.get()
            current_persona.set(persona)
            try:
                db_path = get_db_path()
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    conditions: list = []
                    params: list = []

                    if op_filter:
                        conditions.append("operation = ?")
                        params.append(op_filter)
                    if key_filter:
                        conditions.append("key LIKE ?")
                        params.append(f"%{key_filter}%")
                    if success_filter in ("true", "false"):
                        conditions.append("success = ?")
                        params.append(1 if success_filter == "true" else 0)
                    if since_filter:
                        conditions.append("timestamp >= ?")
                        params.append(since_filter)

                    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

                    # Count
                    cursor.execute(f"SELECT COUNT(*) FROM operations{where}", params)
                    total = cursor.fetchone()[0]

                    # Operation type breakdown
                    cursor.execute(f"SELECT operation, COUNT(*) as cnt FROM operations{where} GROUP BY operation ORDER BY cnt DESC", params)
                    op_breakdown = {r["operation"]: r["cnt"] for r in cursor.fetchall()}

                    # Fetch page
                    offset = (page - 1) * per_page
                    cursor.execute(
                        f"SELECT id, timestamp, operation_id, operation, key, success, error, metadata FROM operations{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                        params + [per_page, offset],
                    )

                    items = []
                    for row in cursor.fetchall():
                        item = dict(row)
                        if item.get("metadata"):
                            try:
                                item["metadata"] = json.loads(item["metadata"])
                            except (json.JSONDecodeError, TypeError):
                                pass
                        items.append(item)

                    return JSONResponse({
                        "success": True,
                        "total": total,
                        "page": page,
                        "per_page": per_page,
                        "total_pages": max(1, -(-total // per_page)),
                        "operation_breakdown": op_breakdown,
                        "items": items,
                    })
            finally:
                current_persona.set(original_persona)
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)


    # ─── Memory Usage Statistics API ─────────────────────────────────

    @mcp.custom_route("/api/memory-usage-stats/{persona}", methods=["GET"])
    async def memory_usage_stats(request: Request):
        """
        Get memory item usage statistics from operations log.
        Shows operation frequency per memory key to identify unused/underused memories.

        Query params:
            sort_by (str): 'frequency', 'last_access', 'key' (default: 'frequency')
            order (str): 'asc', 'desc' (default: 'desc')
            min_days_inactive (int): Filter by days since last access (default: 30)
            max_access_count (int): Filter by max total access count (default: None)
        """
        try:
            persona = request.path_params.get("persona")
            memory_dir = os.path.join(MEMORY_ROOT, persona)
            if not os.path.exists(memory_dir):
                return JSONResponse({"success": False, "error": f"Persona '{persona}' not found"}, status_code=404)

            sort_by = request.query_params.get("sort_by", "frequency")
            order = request.query_params.get("order", "desc")
            min_days_inactive = int(request.query_params.get("min_days_inactive", 0))
            max_access_count = request.query_params.get("max_access_count")
            if max_access_count:
                max_access_count = int(max_access_count)

            original_persona = current_persona.get()
            current_persona.set(persona)
            try:
                db_path = get_db_path()
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    # Get all memory keys with their operations aggregated
                    cursor.execute("""
                        SELECT
                            key,
                            COUNT(*) as total_operations,
                            SUM(CASE WHEN operation = 'create' THEN 1 ELSE 0 END) as create_count,
                            SUM(CASE WHEN operation = 'read' THEN 1 ELSE 0 END) as read_count,
                            SUM(CASE WHEN operation = 'update' THEN 1 ELSE 0 END) as update_count,
                            SUM(CASE WHEN operation = 'delete' THEN 1 ELSE 0 END) as delete_count,
                            SUM(CASE WHEN operation = 'search' THEN 1 ELSE 0 END) as search_count,
                            MIN(timestamp) as first_access,
                            MAX(timestamp) as last_access,
                            julianday('now') - julianday(MAX(timestamp)) as days_since_last_access
                        FROM operations
                        WHERE key IS NOT NULL AND key != ''
                        GROUP BY key
                    """)

                    stats = []
                    now = datetime.now()

                    for row in cursor.fetchall():
                        item = dict(row)

                        # Apply filters
                        if min_days_inactive > 0 and item['days_since_last_access'] < min_days_inactive:
                            continue
                        if max_access_count is not None and item['total_operations'] > max_access_count:
                            continue

                        # Format timestamps
                        item['first_access_formatted'] = item['first_access'][:19] if item['first_access'] else None
                        item['last_access_formatted'] = item['last_access'][:19] if item['last_access'] else None

                        # Get memory content preview if exists
                        cursor.execute("SELECT content FROM memories WHERE key = ?", (item['key'],))
                        mem_row = cursor.fetchone()
                        if mem_row:
                            content = mem_row['content']
                            item['content_preview'] = content[:100] + '...' if len(content) > 100 else content
                            item['exists'] = True
                        else:
                            item['content_preview'] = None
                            item['exists'] = False

                        stats.append(item)

                    # Sort results
                    sort_key_map = {
                        'frequency': 'total_operations',
                        'last_access': 'last_access',
                        'key': 'key'
                    }
                    sort_key = sort_key_map.get(sort_by, 'total_operations')
                    reverse = (order == 'desc')

                    stats.sort(key=lambda x: x[sort_key] if x[sort_key] is not None else '', reverse=reverse)

                    # Calculate summary statistics
                    total_keys = len(stats)
                    low_usage_count = sum(1 for s in stats if s['total_operations'] <= 3)
                    inactive_30d_count = sum(1 for s in stats if s['days_since_last_access'] >= 30)
                    deleted_keys = sum(1 for s in stats if not s['exists'])

                    return JSONResponse({
                        "success": True,
                        "total_keys": total_keys,
                        "summary": {
                            "low_usage_items": low_usage_count,  # ≤3 operations
                            "inactive_30_days": inactive_30d_count,
                            "deleted_keys": deleted_keys
                        },
                        "stats": stats
                    })
            finally:
                current_persona.set(original_persona)
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)


    # ─── Unified Timeline API ────────────────────────────────────────

    @mcp.custom_route("/api/timeline/{persona}", methods=["GET"])
    async def unified_timeline(request: Request):
        """
        Unified timeline merging memories, emotions, physical sensations, and operations
        into a single chronological stream.
        Query params:
            days (int): number of days to look back (default 7, max 90)
            types (str): comma-separated event types to include
                         (memory,emotion,sensation,operation) default: all
            limit (int): max events to return (default 100, max 500)
        """
        try:
            persona = request.path_params.get("persona")
            memory_dir = os.path.join(MEMORY_ROOT, persona)
            if not os.path.exists(memory_dir):
                return JSONResponse({"success": False, "error": f"Persona '{persona}' not found"}, status_code=404)

            days = min(90, max(1, int(request.query_params.get("days", 7))))
            limit = min(500, max(1, int(request.query_params.get("limit", 100))))
            type_str = request.query_params.get("types", "memory,emotion,sensation,operation")
            types = set(t.strip() for t in type_str.split(","))

            since = (datetime.now() - timedelta(days=days)).isoformat()

            original_persona = current_persona.get()
            current_persona.set(persona)
            try:
                db_path = get_db_path()
                # Privacy filter
                from src.utils.config_utils import load_config
                cfg = load_config()
                dashboard_max = cfg.get("privacy", {}).get("dashboard_max_level", "internal")
                _PRIV_RANK = {"public": 0, "internal": 1, "private": 2, "secret": 3}
                max_rank = _PRIV_RANK.get(dashboard_max, 1)
                allowed_levels = [lvl for lvl, rank in _PRIV_RANK.items() if rank <= max_rank]

                events: list = []

                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    if "memory" in types:
                        memory_where = "created_at >= ?"
                        memory_params = [since]
                        if "privacy_level" in memory_columns:
                            placeholders = ",".join("?" for _ in allowed_levels)
                            memory_where += f" AND COALESCE(privacy_level, 'internal') IN ({placeholders})"
                            memory_params += allowed_levels

                        emotion_select = "emotion AS emotion_type" if "emotion" in memory_columns else "NULL AS emotion_type"
                        intensity_select = "emotion_intensity" if "emotion_intensity" in memory_columns else "NULL AS emotion_intensity"
                        cursor.execute(
                            f"""SELECT key, content, {emotion_select}, {intensity_select}, importance,
                                       tags, created_at, action_tag
                                FROM memories
                                WHERE {memory_where}
                                ORDER BY created_at DESC""",
                            memory_params,
                        )
                        for row in cursor.fetchall():
                            content = row["content"] or ""
                            events.append({
                                "type": "memory",
                                "timestamp": row["created_at"],
                                "key": row["key"],
                                "summary": content[:150] + ("..." if len(content) > 150 else ""),
                                "emotion_type": row["emotion_type"],
                                "emotion_intensity": row["emotion_intensity"],
                                "importance": row["importance"],
                                "action_tag": row["action_tag"],
                            })

                    if "emotion" in types:
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='emotion_history'")
                        if cursor.fetchone() is not None:
                            cursor.execute("PRAGMA table_info(emotion_history)")
                            emotion_columns = {row[1] for row in cursor.fetchall()}
                            if "emotion" in emotion_columns:
                                emotion_col = "emotion"
                            elif "emotion_type" in emotion_columns:
                                emotion_col = "emotion_type"
                            else:
                                emotion_col = None

                            trigger_col = "trigger_content" if "trigger_content" in emotion_columns else None
                            if emotion_col:
                                select_cols = f"timestamp, {emotion_col} as emotion_type, emotion_intensity"
                                if trigger_col:
                                    select_cols += f", {trigger_col} as trigger"
                                cursor.execute(
                                    f"SELECT {select_cols} FROM emotion_history WHERE timestamp >= ? ORDER BY timestamp DESC",
                                    (since,),
                                )
                                for row in cursor.fetchall():
                                    trigger_value = row["trigger"] if trigger_col else None
                                    events.append({
                                        "type": "emotion",
                                        "timestamp": row["timestamp"],
                                        "emotion_type": row["emotion_type"],
                                        "emotion_intensity": row["emotion_intensity"],
                                        "trigger": trigger_value,
                                    })

                    if "sensation" in types:
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='physical_sensations_history'")
                        if cursor.fetchone() is not None:
                            cursor.execute("PRAGMA table_info(physical_sensations_history)")
                            sensation_columns = {row[1] for row in cursor.fetchall()}
                            select_cols = ["timestamp", "fatigue", "warmth", "arousal"]
                            if "custom_sensations" in sensation_columns:
                                select_cols.append("custom_sensations")
                            cursor.execute(
                                f"SELECT {', '.join(select_cols)} FROM physical_sensations_history WHERE timestamp >= ? ORDER BY timestamp DESC",
                                (since,),
                            )
                            for row in cursor.fetchall():
                                events.append({
                                    "type": "sensation",
                                    "timestamp": row["timestamp"],
                                    "fatigue": row["fatigue"],
                                    "warmth": row["warmth"],
                                    "arousal": row["arousal"],
                                })

                    if "operation" in types:
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='operations'")
                        if cursor.fetchone() is not None:
                            cursor.execute(
                                "SELECT timestamp, operation, key, success, error FROM operations WHERE timestamp >= ? ORDER BY timestamp DESC",
                                (since,),
                            )
                            for row in cursor.fetchall():
                                events.append({
                                    "type": "operation",
                                    "timestamp": row["timestamp"],
                                    "operation": row["operation"],
                                    "key": row["key"],
                                    "success": bool(row["success"]),
                                    "error": row["error"],
                                })

                # Sort all events by timestamp descending
                events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
                events = events[:limit]

                # Summary stats
                type_counts = Counter(e["type"] for e in events)

                return JSONResponse({
                    "success": True,
                    "days": days,
                    "total_events": len(events),
                    "type_counts": dict(type_counts),
                    "events": events,
                })
            finally:
                current_persona.set(original_persona)
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

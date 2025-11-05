"""
Dashboard and HTTP API for Memory MCP
Provides FastAPI routes for web dashboard
"""

import os
import glob
import json
import sqlite3
import re
from collections import Counter
from datetime import datetime, timedelta
from contextvars import ContextVar
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse

# Core imports
from core import load_persona_context, calculate_time_diff

# Utility imports
from src.utils.persona_utils import get_db_path, get_current_persona, current_persona
from src.utils.vector_utils import get_vector_count


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
            "environment": context.get("environment", "unknown")
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
                except:
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
    """Core function to get memory stats data for a specific persona."""
    original_persona = current_persona.get()
    current_persona.set(persona)
    
    try:
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

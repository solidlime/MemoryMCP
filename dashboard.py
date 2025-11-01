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
from persona_utils import get_db_path, get_current_persona, current_persona
from vector_utils import get_vector_count


# Get script directory for output files
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_ROOT = os.path.join(SCRIPT_DIR, "memory")


def db_count_entries() -> int:
    """Count total entries in database."""
    from db_utils import db_count_entries as db_count_impl
    return db_count_impl(get_db_path())


def db_sum_content_chars() -> int:
    """Sum total content characters in database."""
    from db_utils import db_sum_content_chars as db_sum_impl
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

import os
from contextvars import ContextVar
from fastmcp.server.dependencies import get_http_request

from src.utils.config_utils import ensure_directory, ensure_memory_root

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Persona context variable (thread-safe, request-scoped)
current_persona: ContextVar[str] = ContextVar('current_persona', default='default')

def get_current_persona() -> str:
    """Get current persona from HTTP request header or context variable"""
    try:
        request = get_http_request()
        if request:
            persona = request.headers.get('x-persona', 'default')
            return persona
    except Exception:
        pass
    return current_persona.get()

def get_persona_dir(persona: str | None = None) -> str:
    """Get persona-specific directory path"""
    if persona is None:
        persona = get_current_persona()
    safe_persona = persona.replace('/', '_').replace('\\', '_')
    base_dir = ensure_memory_root()
    persona_dir = os.path.join(base_dir, safe_persona)
    ensure_directory(persona_dir)
    return persona_dir

def get_db_path(persona: str | None = None) -> str:
    """Get persona-specific SQLite database path with legacy migration"""
    if persona is None:
        persona = get_current_persona()

    persona_dir = get_persona_dir(persona)
    new_db_path = os.path.join(persona_dir, "memory.sqlite")

    # Legacy path: memory/{persona}.sqlite
    safe_persona = persona.replace('/', '_').replace('\\', '_')
    legacy_db_path = os.path.join(SCRIPT_DIR, "memory", f"{safe_persona}.sqlite")

    if os.path.exists(legacy_db_path) and not os.path.exists(new_db_path):
        try:
            os.replace(legacy_db_path, new_db_path)
        except Exception:
            # Best-effort; keep going
            pass

    return new_db_path

def get_vector_store_path(persona: str | None = None) -> str:
    if persona is None:
        persona = get_current_persona()
    return os.path.join(get_persona_dir(persona), "vector_store")

def get_persona_context_path(persona: str | None = None) -> str:
    if persona is None:
        persona = get_current_persona()
    return os.path.join(get_persona_dir(persona), "persona_context.json")

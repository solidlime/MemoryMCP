"""
Persona context management for memory-mcp.

This module handles loading, saving, and managing persona-specific context data.
"""

import json
import os
import shutil
from typing import Optional

from persona_utils import get_current_persona, get_persona_context_path


def _log_progress(message: str) -> None:
    """Internal logging function."""
    print(message, flush=True)


def load_persona_context(persona: Optional[str] = None) -> dict:
    """
    Load persona context from JSON file.
    
    Args:
        persona: Persona name (defaults to current persona)
    
    Returns:
        dict with persona context data
    """
    if persona is None:
        persona = get_current_persona()
    
    context_path = get_persona_context_path(persona)
    
    # Default context structure
    default_context = {
        "user_info": {
            "name": "User",
            "nickname": None,
            "preferred_address": None
        },
        "persona_info": {
            "name": persona,
            "nickname": None,
            "preferred_address": None
        },
        "last_conversation_time": None,
        "current_emotion": "neutral",
        "physical_state": "normal",
        "mental_state": "calm",
        "environment": "unknown",
        "relationship_status": "normal"
    }
    
    try:
        if os.path.exists(context_path):
            with open(context_path, 'r', encoding='utf-8') as f:
                context = json.load(f)
                _log_progress(f"✅ Loaded persona context from {context_path}")
                return context
        else:
            # Create default context file
            save_persona_context(default_context, persona)
            _log_progress(f"✅ Created default persona context at {context_path}")
            return default_context
    except Exception as e:
        _log_progress(f"❌ Failed to load persona context: {e}")
        return default_context


def save_persona_context(context: dict, persona: Optional[str] = None) -> bool:
    """
    Save persona context to JSON file.
    
    Args:
        context: dict with persona context data
        persona: persona name (defaults to current persona)
    
    Returns:
        bool indicating success
    """
    if persona is None:
        persona = get_current_persona()
    
    context_path = get_persona_context_path(persona)
    
    try:
        # Create backup if file exists
        if os.path.exists(context_path):
            backup_path = f"{context_path}.backup"
            shutil.copy2(context_path, backup_path)
        
        # Save context
        with open(context_path, 'w', encoding='utf-8') as f:
            json.dump(context, f, indent=2, ensure_ascii=False)
        
        _log_progress(f"✅ Saved persona context to {context_path}")
        return True
    except Exception as e:
        _log_progress(f"❌ Failed to save persona context: {e}")
        return False

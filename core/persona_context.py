"""
Persona context management for memory-mcp.

This module handles loading, saving, and managing persona-specific context data.
"""

import json
import os
import shutil
from typing import Optional

from src.utils.persona_utils import get_current_persona, get_persona_context_path
from src.utils.logging_utils import log_progress


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
        "current_emotion_intensity": None,
        "physical_state": "normal",
        "mental_state": "calm",
        "environment": "unknown",
        "relationship_status": "normal",
        "current_action_tag": None,
        "physical_sensations": {
            "fatigue": 0.0,
            "warmth": 0.5,
            "arousal": 0.0,
            "touch_response": "normal",
            "heart_rate_metaphor": "calm"
        }
        # Note: emotion_history, anniversaries moved to SQLite tables
        # - emotion_history -> emotion_history table
        # - anniversaries -> memories table with 'anniversary' tag
    }

    try:
        if os.path.exists(context_path):
            with open(context_path, 'r', encoding='utf-8') as f:
                context = json.load(f)
                log_progress(f"✅ Loaded persona context from {context_path}")
                return context
        else:
            # Create default context file
            save_persona_context(default_context, persona)
            log_progress(f"✅ Created default persona context at {context_path}")
            return default_context
    except Exception as e:
        log_progress(f"❌ Failed to load persona context: {e}")
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

        log_progress(f"✅ Saved persona context to {context_path}")
        return True
    except Exception as e:
        log_progress(f"❌ Failed to save persona context: {e}")
        return False


def update_last_conversation_time(persona: Optional[str] = None) -> None:
    """
    Update last_conversation_time to current time.
    Should be called at the start of every tool operation.

    Args:
        persona: Persona name (defaults to current persona)
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.utils.config_utils import load_config

    if persona is None:
        persona = get_current_persona()

    config = load_config()
    timezone = config.get("timezone", "Asia/Tokyo")

    context = load_persona_context(persona)
    context["last_conversation_time"] = datetime.now(ZoneInfo(timezone)).isoformat()
    save_persona_context(context, persona)

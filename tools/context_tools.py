"""
Persona context management tools for memory-mcp.

This module provides MCP tools for managing and querying persona context state.
"""

from core import (
    get_current_time,
    calculate_time_diff,
    load_persona_context,
    save_persona_context,
)
from persona_utils import get_current_persona


def _log_progress(message: str) -> None:
    """Internal logging function."""
    print(message, flush=True)


async def get_time_since_last_conversation() -> str:
    """
    Get the time elapsed since the last conversation.
    Automatically updates the last conversation time to the current time.
    
    This tool helps the AI understand how much time has passed and respond 
    with appropriate emotional awareness (e.g., "It's been a while!", "Welcome back!").
    
    Returns:
        Formatted string with time elapsed information
    """
    try:
        persona = get_current_persona()
        
        # Load persona context
        context = load_persona_context(persona)
        
        last_time_str = context.get("last_conversation_time")
        current_time = get_current_time()
        
        # Calculate time difference
        if last_time_str:
            time_diff = calculate_time_diff(last_time_str)
            result = f"⏰ 前回の会話から {time_diff['formatted_string']} が経過しました。\n"
            result += f"📅 前回: {last_time_str[:19]}\n"
            result += f"📅 現在: {current_time.isoformat()[:19]}\n"
        else:
            result = "🆕 これが最初の会話です！\n"
            result += f"📅 現在: {current_time.isoformat()[:19]}\n"
        
        # Update last conversation time
        context["last_conversation_time"] = current_time.isoformat()
        save_persona_context(context, persona)
        
        return result
    except Exception as e:
        _log_progress(f"❌ Failed to get time since last conversation: {e}")
        return f"Failed to get time information: {str(e)}"


async def get_persona_context() -> str:
    """
    Get current persona context including emotion state, physical/mental state, and environment.
    Use this to understand the current state and maintain consistency across conversation sessions.
    
    Returns:
        Formatted string containing:
        - user_info: User's name, nickname, preferred way to be addressed
        - persona_info: Persona's name, nickname, preferred way to be called
        - current_emotion: Current emotional state (joy, sadness, neutral, etc.)
        - physical_state: Current physical condition (normal, tired, energetic, etc.)
        - mental_state: Current mental/psychological state (calm, anxious, focused, etc.)
        - environment: Current environment or location (home, office, unknown, etc.)
        - last_conversation_time: When the last conversation occurred
        - relationship_status: Current relationship status
    """
    try:
        persona = get_current_persona()
        context = load_persona_context(persona)
        
        # Format response
        result = f"📋 Persona Context (persona: {persona}):\n\n"
        
        # User Information
        user_info = context.get('user_info', {})
        result += f"👤 User Information:\n"
        result += f"   Name: {user_info.get('name', 'Unknown')}\n"
        if user_info.get('nickname'):
            result += f"   Nickname: {user_info.get('nickname')}\n"
        if user_info.get('preferred_address'):
            result += f"   Preferred Address: {user_info.get('preferred_address')}\n"
        
        # Persona Information
        persona_info = context.get('persona_info', {})
        result += f"\n🎭 Persona Information:\n"
        result += f"   Name: {persona_info.get('name', persona)}\n"
        if persona_info.get('nickname'):
            result += f"   Nickname: {persona_info.get('nickname')}\n"
        if persona_info.get('preferred_address'):
            result += f"   How to be called: {persona_info.get('preferred_address')}\n"
        
        # Current States
        result += f"\n🎨 Current States:\n"
        result += f"   Emotion: {context.get('current_emotion', 'neutral')}\n"
        result += f"   Physical: {context.get('physical_state', 'normal')}\n"
        result += f"   Mental: {context.get('mental_state', 'calm')}\n"
        result += f"   Environment: {context.get('environment', 'unknown')}\n"
        result += f"   Relationship: {context.get('relationship_status', 'normal')}\n"
        
        # Time Information
        if context.get('last_conversation_time'):
            time_diff = calculate_time_diff(context['last_conversation_time'])
            result += f"\n⏰ Last Conversation: {time_diff['formatted_string']}前\n"
        else:
            result += f"\n⏰ Last Conversation: First time\n"
        
        return result
    except Exception as e:
        _log_progress(f"❌ Failed to get persona context: {e}")
        return f"Failed to get persona context: {str(e)}"

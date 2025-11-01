"""
Core utilities for memory-mcp.

This package provides essential utilities for time operations, persona context management,
and memory database operations.
"""

from .time_utils import get_current_time, parse_date_query, calculate_time_diff
from .persona_context import load_persona_context, save_persona_context
from .memory_db import (
    load_memory_from_db,
    save_memory_to_db,
    delete_memory_from_db,
    create_memory_entry,
    generate_auto_key,
    log_operation,
)

__all__ = [
    # Time utilities
    'get_current_time',
    'parse_date_query', 
    'calculate_time_diff',
    # Persona context
    'load_persona_context',
    'save_persona_context',
    # Memory database
    'load_memory_from_db',
    'save_memory_to_db',
    'delete_memory_from_db',
    'create_memory_entry',
    'generate_auto_key',
    'log_operation',
]

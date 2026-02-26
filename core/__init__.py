"""
Core utilities for memory-mcp.

This package provides essential utilities for time operations, persona context management,
and memory database operations.
"""

from .time_utils import (
    get_current_time,
    parse_date_query,
    calculate_time_diff,
    format_datetime_for_display,
    get_current_time_display,
    get_datetime_context,
)
from .persona_context import load_persona_context, save_persona_context, update_last_conversation_time
from .memory_db import (
    load_memory_from_db,
    save_memory_to_db,
    delete_memory_from_db,
    create_memory_entry,
    generate_auto_key,
    log_operation,
)
from src.utils.logging_utils import log_progress
from .forgetting import (
    start_ebbinghaus_worker,
    stop_ebbinghaus_worker,
    boost_on_recall,
    run_decay_pass,
    ebbinghaus_retention,
    compute_strength,
)
from .user_state_db import (
    update_user_state,
    update_user_state_bulk,
    get_current_user_state,
    get_user_state_history,
    USER_STATE_KEYS,
)
from .memory_blocks_db import (
    read_block,
    write_block,
    delete_block,
    list_blocks,
    STANDARD_BLOCKS,
)

__all__ = [
    # Time utilities
    'get_current_time',
    'parse_date_query',
    'calculate_time_diff',
    'format_datetime_for_display',
    'get_current_time_display',
    'get_datetime_context',
    # Persona context
    'load_persona_context',
    'save_persona_context',
    'update_last_conversation_time',
    # Memory database
    'load_memory_from_db',
    'save_memory_to_db',
    'delete_memory_from_db',
    'create_memory_entry',
    'generate_auto_key',
    'log_operation',
    # Logging
    'log_progress',
    # Ebbinghaus forgetting curve
    'start_ebbinghaus_worker',
    'stop_ebbinghaus_worker',
    'boost_on_recall',
    'run_decay_pass',
    'ebbinghaus_retention',
    'compute_strength',
    # Bi-temporal user state
    'update_user_state',
    'update_user_state_bulk',
    'get_current_user_state',
    'get_user_state_history',
    'USER_STATE_KEYS',
    # Named memory blocks
    'read_block',
    'write_block',
    'delete_block',
    'list_blocks',
    'STANDARD_BLOCKS',
]

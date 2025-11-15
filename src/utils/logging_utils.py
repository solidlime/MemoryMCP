"""Centralized logging utilities for Memory-MCP project.

This module provides unified logging functionality to avoid code duplication
across the project.
"""

import sys
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


def log_progress(message: str, level: LogLevel = "INFO") -> None:
    """Log progress message to stdout with flush.
    
    Args:
        message: Message to log
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    
    Examples:
        log_progress("✅ Operation completed")
        log_progress("❌ Error occurred", level="ERROR")
    """
    print(f"[{level}] {message}", flush=True)


def log_debug(message: str) -> None:
    """Log debug message."""
    log_progress(message, level="DEBUG")


def log_info(message: str) -> None:
    """Log info message."""
    log_progress(message, level="INFO")


def log_warning(message: str) -> None:
    """Log warning message."""
    log_progress(message, level="WARNING")


def log_error(message: str) -> None:
    """Log error message."""
    log_progress(message, level="ERROR")

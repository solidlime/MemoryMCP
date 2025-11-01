"""
Time utility functions for memory-mcp.

This module provides timezone-aware time operations and date parsing utilities.
"""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Tuple

from config_utils import load_config


def _log_progress(message: str) -> None:
    """Internal logging function."""
    print(message, flush=True)


def get_current_time() -> datetime:
    """
    Get current time in configured timezone.
    Returns timezone-aware datetime object.
    """
    config = load_config()
    timezone_str = config.get("timezone", "Asia/Tokyo")
    try:
        tz = ZoneInfo(timezone_str)
        return datetime.now(tz)
    except Exception as e:
        _log_progress(f"⚠️  Invalid timezone '{timezone_str}', using UTC: {e}")
        return datetime.now(ZoneInfo("UTC"))


def parse_date_query(date_query: str) -> Tuple[datetime, datetime]:
    """
    Parse date query string into start and end datetime objects.
    
    Args:
        date_query: Date query string (e.g., "今日", "昨日", "2025-10-01", "2025-10-01..2025-10-31")
    
    Returns:
        tuple: (start_date, end_date) as timezone-aware datetime objects
    
    Raises:
        ValueError: If date format is invalid
    """
    current_time = get_current_time()
    start_date = None
    end_date = None
    
    # Handle relative date expressions
    if date_query in ["今日", "today"]:
        start_date = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif date_query in ["昨日", "yesterday"]:
        yesterday = current_time - timedelta(days=1)
        start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif date_query in ["今週", "this week"]:
        # Start of week (Monday)
        start_date = current_time - timedelta(days=current_time.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = current_time
    elif date_query in ["先週", "last week"]:
        # Last week Monday to Sunday
        start_date = current_time - timedelta(days=current_time.weekday() + 7)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59)
    elif date_query in ["今月", "this month"]:
        start_date = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = current_time
    elif "日前" in date_query or "days ago" in date_query:
        # Extract number of days
        match = re.search(r'(\d+)', date_query)
        if match:
            days = int(match.group(1))
            target_date = current_time - timedelta(days=days)
            start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            raise ValueError(f"Could not parse days from: '{date_query}'")
    elif ".." in date_query:
        # Date range: "YYYY-MM-DD..YYYY-MM-DD"
        parts = date_query.split("..")
        if len(parts) == 2:
            start_date = datetime.fromisoformat(parts[0])
            end_date = datetime.fromisoformat(parts[1])
            # Make timezone-aware
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=current_time.tzinfo)
            if end_date.tzinfo is None:
                end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=current_time.tzinfo)
        else:
            raise ValueError(f"Invalid date range format: '{date_query}' (expected YYYY-MM-DD..YYYY-MM-DD)")
    else:
        # Specific date: "YYYY-MM-DD"
        try:
            target_date = datetime.fromisoformat(date_query)
            if target_date.tzinfo is None:
                target_date = target_date.replace(tzinfo=current_time.tzinfo)
            start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            raise ValueError(f"Invalid date format: '{date_query}'. Use 'YYYY-MM-DD', '今日', '昨日', '3日前', or 'YYYY-MM-DD..YYYY-MM-DD'")
    
    if start_date is None or end_date is None:
        raise ValueError(f"Could not parse date query: '{date_query}'")
    
    return (start_date, end_date)


def calculate_time_diff(start_time: str, end_time: Optional[str] = None) -> dict:
    """
    Calculate time difference between two timestamps.
    
    Args:
        start_time: ISO format timestamp string
        end_time: ISO format timestamp string (defaults to current time)
    
    Returns:
        dict with keys: days, hours, minutes, total_hours, formatted_string
    """
    try:
        # Parse start time
        if isinstance(start_time, str):
            start_dt = datetime.fromisoformat(start_time)
        else:
            start_dt = start_time
        
        # Make start_dt timezone-aware if it's naive
        if start_dt.tzinfo is None:
            config = load_config()
            timezone_str = config.get("timezone", "Asia/Tokyo")
            tz = ZoneInfo(timezone_str)
            start_dt = start_dt.replace(tzinfo=tz)
        
        # Get end time (current time if not specified)
        if end_time is None:
            end_dt = get_current_time()
        elif isinstance(end_time, str):
            end_dt = datetime.fromisoformat(end_time)
            # Make end_dt timezone-aware if it's naive
            if end_dt.tzinfo is None:
                config = load_config()
                timezone_str = config.get("timezone", "Asia/Tokyo")
                tz = ZoneInfo(timezone_str)
                end_dt = end_dt.replace(tzinfo=tz)
        else:
            end_dt = end_time
        
        # Calculate difference
        delta = end_dt - start_dt
        
        total_seconds = delta.total_seconds()
        days = delta.days
        hours = int((total_seconds % 86400) / 3600)
        minutes = int((total_seconds % 3600) / 60)
        total_hours = total_seconds / 3600
        
        # Format string
        parts = []
        if days > 0:
            parts.append(f"{days}日")
        if hours > 0:
            parts.append(f"{hours}時間")
        if minutes > 0:
            parts.append(f"{minutes}分")
        
        formatted = " ".join(parts) if parts else "1分未満"
        
        return {
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "total_hours": total_hours,
            "formatted_string": formatted
        }
    except Exception as e:
        _log_progress(f"❌ Failed to calculate time diff: {e}")
        return {
            "days": 0,
            "hours": 0,
            "minutes": 0,
            "total_hours": 0,
            "formatted_string": "計算エラー"
        }

"""
Time utility functions for memory-mcp.

This module provides timezone-aware time operations and date parsing utilities.
"""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Tuple

from src.utils.config_utils import load_config


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


def format_datetime_for_display(dt_str: str) -> str:
    """
    Convert ISO format datetime to user-friendly format with weekday.
    
    Args:
        dt_str: ISO format datetime string (RFC 3339)
    
    Returns:
        Formatted string like "2025-10-29(Wed) 22:03:47 JST"
    
    Example:
        >>> format_datetime_for_display("2025-10-29T22:03:47+09:00")
        "2025-10-29(Wed) 22:03:47 JST"
    """
    try:
        dt = datetime.fromisoformat(dt_str)
        
        # Get weekday abbreviation
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        weekday_abbr = weekdays[dt.weekday()]
        
        # Get timezone abbreviation
        tz_name = dt.tzname() or "UTC"
        
        # Format: YYYY-MM-DD(Weekday) HH:MM:SS TZ
        formatted = f"{dt.strftime('%Y-%m-%d')}({weekday_abbr}) {dt.strftime('%H:%M:%S')} {tz_name}"
        
        return formatted
    except Exception as e:
        _log_progress(f"❌ Failed to format datetime: {e}")
        return dt_str


def get_datetime_context(dt_str: str) -> dict:
    """
    Extract searchable datetime context from ISO format datetime.
    
    Args:
        dt_str: ISO format datetime string (RFC 3339)
    
    Returns:
        dict with weekday, month, year, formatted strings for search
    
    Example:
        >>> get_datetime_context("2025-10-29T22:03:47+09:00")
        {
            "weekday_en": "Wednesday",
            "weekday_ja": "水曜日",
            "weekday_abbr": "Wed",
            "month": "10",
            "month_name": "October",
            "year": "2025",
            "date": "2025-10-29",
            "display": "2025-10-29(Wed) 22:03:47 JST"
        }
    """
    try:
        dt = datetime.fromisoformat(dt_str)
        
        # Weekday names
        weekdays_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekdays_ja = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
        weekdays_abbr = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        # Month names
        months_en = ["January", "February", "March", "April", "May", "June", 
                    "July", "August", "September", "October", "November", "December"]
        
        return {
            "weekday_en": weekdays_en[dt.weekday()],
            "weekday_ja": weekdays_ja[dt.weekday()],
            "weekday_abbr": weekdays_abbr[dt.weekday()],
            "month": dt.strftime('%m'),
            "month_name": months_en[dt.month - 1],
            "year": dt.strftime('%Y'),
            "date": dt.strftime('%Y-%m-%d'),
            "display": format_datetime_for_display(dt_str)
        }
    except Exception as e:
        _log_progress(f"❌ Failed to get datetime context: {e}")
        return {
            "weekday_en": "Unknown",
            "weekday_ja": "不明",
            "weekday_abbr": "Unknown",
            "month": "00",
            "month_name": "Unknown",
            "year": "0000",
            "date": "0000-00-00",
            "display": dt_str
        }


def get_current_time_display() -> str:
    """
    Get current time in user-friendly display format with weekday.
    
    Returns:
        Formatted string like "2025-10-29(Wed) 22:03:47 JST"
    """
    current = get_current_time()
    return format_datetime_for_display(current.isoformat())

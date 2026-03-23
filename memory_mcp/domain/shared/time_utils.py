from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_DEFAULT_TZ = "Asia/Tokyo"


def get_now(tz: str = _DEFAULT_TZ) -> datetime:
    """Return current time in the given timezone."""
    return datetime.now(ZoneInfo(tz))


def format_iso(dt: datetime) -> str:
    """Format datetime as ISO 8601 string with timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(_DEFAULT_TZ))
    return dt.isoformat()


def parse_iso(s: str) -> datetime:
    """Parse an ISO 8601 datetime string."""
    return datetime.fromisoformat(s)


def generate_memory_key(prefix: str = "memory") -> str:
    """Generate a timestamped memory key: {prefix}_YYYYMMDDHHMMSS."""
    now = get_now()
    return f"{prefix}_{now.strftime('%Y%m%d%H%M%S')}"


def relative_time_str(dt: datetime, now: datetime | None = None) -> str:
    """Return a Japanese relative time string (e.g. '2時間前', '3日前')."""
    if now is None:
        now = get_now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(_DEFAULT_TZ))
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo(_DEFAULT_TZ))

    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 0:
        return "未来"
    if seconds < 60:
        return "たった今"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}分前"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours}時間前"
    if seconds < 2592000:
        days = seconds // 86400
        return f"{days}日前"
    if seconds < 31536000:
        months = seconds // 2592000
        return f"{months}ヶ月前"
    years = seconds // 31536000
    return f"{years}年前"


def parse_date_range(range_str: str) -> tuple[datetime, datetime]:
    """Parse date range strings like '7d', '30d', '2025-01-01~2025-06-01'.

    Returns (start, end) as timezone-aware datetimes.
    """
    now = get_now()

    # Pattern: Nd (N days ago to now)
    day_match = re.match(r"^(\d+)d$", range_str.strip())
    if day_match:
        days = int(day_match.group(1))
        start = now - timedelta(days=days)
        return (start, now)

    # Pattern: Nw (N weeks ago to now)
    week_match = re.match(r"^(\d+)w$", range_str.strip())
    if week_match:
        weeks = int(week_match.group(1))
        start = now - timedelta(weeks=weeks)
        return (start, now)

    # Pattern: Nm (N months ago to now, approximate)
    month_match = re.match(r"^(\d+)m$", range_str.strip())
    if month_match:
        months = int(month_match.group(1))
        start = now - timedelta(days=months * 30)
        return (start, now)

    # Pattern: YYYY-MM-DD~YYYY-MM-DD
    range_match = re.match(
        r"^(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})$", range_str.strip()
    )
    if range_match:
        tz = ZoneInfo(_DEFAULT_TZ)
        start = datetime.strptime(range_match.group(1), "%Y-%m-%d").replace(tzinfo=tz)
        end = datetime.strptime(range_match.group(2), "%Y-%m-%d").replace(tzinfo=tz)
        # Set end to end of day
        end = end.replace(hour=23, minute=59, second=59)
        return (start, end)

    raise ValueError(f"Cannot parse date range: {range_str!r}")

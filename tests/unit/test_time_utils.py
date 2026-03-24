"""Tests for time_utils module."""

import re
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from memory_mcp.domain.shared.time_utils import (
    format_iso,
    generate_memory_key,
    get_now,
    parse_date_range,
    parse_iso,
    relative_time_str,
)

TZ = ZoneInfo("Asia/Tokyo")


def _fixed_now() -> datetime:
    """Return a fixed datetime for deterministic tests: 2025-06-15 14:30:00 JST (Sunday)."""
    return datetime(2025, 6, 15, 14, 30, 0, tzinfo=TZ)


class TestGetNow:
    def test_returns_aware_datetime(self):
        now = get_now()
        assert now.tzinfo is not None

    def test_default_timezone_is_tokyo(self):
        now = get_now()
        assert str(now.tzinfo) == "Asia/Tokyo"

    def test_custom_timezone(self):
        now = get_now("UTC")
        assert str(now.tzinfo) == "UTC"


class TestFormatIso:
    def test_aware_datetime(self):
        dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=TZ)
        result = format_iso(dt)
        assert "2025-01-15" in result
        assert "10:30:00" in result
        assert "+" in result  # timezone offset

    def test_naive_datetime_gets_tokyo_tz(self):
        dt = datetime(2025, 1, 15, 10, 30, 0)
        result = format_iso(dt)
        assert "+09:00" in result


class TestParseIso:
    def test_roundtrip(self):
        dt = datetime(2025, 3, 20, 15, 45, 0, tzinfo=TZ)
        iso_str = format_iso(dt)
        parsed = parse_iso(iso_str)
        assert parsed.year == 2025
        assert parsed.month == 3
        assert parsed.day == 20

    def test_parse_basic_iso(self):
        dt = parse_iso("2025-01-01T00:00:00+09:00")
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 1


class TestGenerateMemoryKey:
    def test_default_prefix(self):
        key = generate_memory_key()
        assert key.startswith("memory_")
        assert re.match(r"^memory_\d{14}_\d{6}_[0-9a-f]{8}$", key)

    def test_custom_prefix(self):
        key = generate_memory_key("emotion")
        assert key.startswith("emotion_")
        assert re.match(r"^emotion_\d{14}_\d{6}_[0-9a-f]{8}$", key)

    def test_uniqueness_within_same_second(self):
        keys = [generate_memory_key() for _ in range(100)]
        assert len(set(keys)) == 100

    def test_format_structure(self):
        key = generate_memory_key()
        parts = key.split("_")
        assert len(parts) == 4
        assert parts[0] == "memory"
        assert len(parts[1]) == 14 and parts[1].isdigit()
        assert len(parts[2]) == 6 and parts[2].isdigit()
        assert len(parts[3]) == 8 and re.match(r"^[0-9a-f]{8}$", parts[3])

    def test_not_empty(self):
        key = generate_memory_key()
        assert key


class TestRelativeTimeStr:
    def test_just_now(self):
        now = _fixed_now()
        dt = now - timedelta(seconds=10)
        assert relative_time_str(dt, now) == "たった今"

    def test_minutes_ago(self):
        now = _fixed_now()
        dt = now - timedelta(minutes=5)
        assert relative_time_str(dt, now) == "5分前"

    def test_hours_ago(self):
        now = _fixed_now()
        dt = now - timedelta(hours=3)
        assert relative_time_str(dt, now) == "3時間前"

    def test_days_ago(self):
        now = _fixed_now()
        dt = now - timedelta(days=7)
        assert relative_time_str(dt, now) == "7日前"

    def test_months_ago(self):
        now = _fixed_now()
        dt = now - timedelta(days=60)
        assert relative_time_str(dt, now) == "2ヶ月前"

    def test_years_ago(self):
        now = _fixed_now()
        dt = now - timedelta(days=400)
        assert relative_time_str(dt, now) == "1年前"

    def test_future(self):
        now = _fixed_now()
        dt = now + timedelta(hours=1)
        assert relative_time_str(dt, now) == "未来"

    def test_naive_datetime_handled(self):
        now = _fixed_now()
        dt_naive = datetime(2025, 6, 15, 14, 0, 0)  # naive
        result = relative_time_str(dt_naive, now)
        assert "分前" in result


class TestParseDateRange:
    """parse_date_range の全パターンテスト。get_now() をモックして固定日時で検証。"""

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_none_input(self, _mock):
        start, end = parse_date_range(None)
        assert start is None
        assert end is None

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_empty_string(self, _mock):
        start, end = parse_date_range("")
        assert start is None
        assert end is None

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_yesterday(self, _mock):
        start, end = parse_date_range("昨日")
        assert start is not None and end is not None
        assert start.day == 14
        assert start.hour == 0 and start.minute == 0
        assert end.day == 14
        assert end.hour == 23 and end.minute == 59

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_day_before_yesterday(self, _mock):
        start, end = parse_date_range("一昨日")
        assert start is not None and end is not None
        assert start.day == 13
        assert end.day == 13

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_ototoi(self, _mock):
        start, end = parse_date_range("おととい")
        assert start is not None and end is not None
        assert start.day == 13

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_last_week(self, _mock):
        """2025-06-15 は日曜。先週=6/2(月)〜6/8(日)。"""
        start, end = parse_date_range("先週")
        assert start is not None and end is not None
        assert start.month == 6 and start.day == 2
        assert end.month == 6 and end.day == 8

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_last_month(self, _mock):
        start, end = parse_date_range("先月")
        assert start is not None and end is not None
        assert start.month == 5 and start.day == 1
        assert end.month == 5 and end.day == 31

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_this_morning(self, _mock):
        start, end = parse_date_range("今朝")
        assert start is not None and end is not None
        assert start.hour == 0
        assert end.hour == 12

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_n_days_ago_arabic(self, _mock):
        start, end = parse_date_range("3日前")
        assert start is not None and end is not None
        assert start.day == 12
        assert end.day == 12

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_n_days_ago_kanji(self, _mock):
        start, end = parse_date_range("三日前")
        assert start is not None and end is not None
        assert start.day == 12

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_n_weeks_ago(self, _mock):
        start, end = parse_date_range("2週間前")
        assert start is not None and end is not None
        # 2 weeks ago from 2025-06-15:
        # end = today_start - timedelta(weeks=2-1) = June 8
        # start = end - timedelta(weeks=1) = June 1
        assert start.day == 1
        assert end.day == 8

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_n_months_ago(self, _mock):
        start, end = parse_date_range("3ヶ月前")
        assert start is not None and end is not None
        assert start.month == 3 and start.day == 1
        assert end.month == 3 and end.day == 31

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_today(self, _mock):
        """'今日' → today_start to now."""
        start, end = parse_date_range("今日")
        assert start is not None and end is not None
        assert start.day == 15 and start.hour == 0
        assert end.day == 15

    @patch("memory_mcp.domain.shared.time_utils.get_now", return_value=_fixed_now())
    def test_relative_days_format(self, _mock):
        start, end = parse_date_range("7d")
        assert start is not None and end is not None
        diff = end - start
        assert abs(diff.days - 7) <= 1

    def test_absolute_range(self):
        start, end = parse_date_range("2025-01-01~2025-01-31")
        assert start is not None and end is not None
        assert start.year == 2025 and start.month == 1 and start.day == 1
        assert end.year == 2025 and end.month == 1 and end.day == 31

    def test_unknown_returns_none(self):
        start, end = parse_date_range("なにこれ")
        assert start is None and end is None

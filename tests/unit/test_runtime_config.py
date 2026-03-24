"""Tests for RuntimeConfigManager."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from memory_mcp.config.runtime_config import SETTINGS_META, RuntimeConfigManager

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the singleton before and after each test."""
    RuntimeConfigManager.reset()
    yield
    RuntimeConfigManager.reset()


@pytest.fixture()
def tmp_data_dir(tmp_path: Path):
    """Provide a temporary data directory and patch get_settings to use it."""
    from memory_mcp.config.settings import Settings

    mock_settings = Settings(data_dir=str(tmp_path))
    with patch("memory_mcp.config.runtime_config.get_settings", return_value=mock_settings):
        yield tmp_path


def test_get_all_returns_all_categories(tmp_data_dir: Path):
    """All categories defined in SETTINGS_META should appear in get_all()."""
    mgr = RuntimeConfigManager()
    result = mgr.get_all()

    assert "settings" in result
    assert "reload_status" in result
    for category in SETTINGS_META:
        assert category in result["settings"], f"Missing category: {category}"
        for key in SETTINGS_META[category]:
            assert key in result["settings"][category], f"Missing key: {category}.{key}"
            entry = result["settings"][category][key]
            assert "value" in entry
            assert "source" in entry


def test_get_effective_value_default(tmp_data_dir: Path):
    """Without env or overrides, the default value from Settings should be returned."""
    mgr = RuntimeConfigManager()

    value, source = mgr.get_effective_value("general", "timezone")
    assert source == "default"
    assert value == "Asia/Tokyo"

    value, source = mgr.get_effective_value("embedding", "model")
    assert source == "default"
    assert value == "cl-nagoya/ruri-v3-30m"


def test_update_hot_reloadable(tmp_data_dir: Path):
    """Updating a hot-reloadable setting should succeed and be reflected."""
    mgr = RuntimeConfigManager()

    result = mgr.update("general", "timezone", "US/Eastern")
    assert result["success"] is True

    value, source = mgr.get_effective_value("general", "timezone")
    assert value == "US/Eastern"
    assert source == "override"


def test_update_non_hot_reloadable(tmp_data_dir: Path):
    """Updating a non-hot-reloadable setting should fail with restart_required."""
    mgr = RuntimeConfigManager()

    result = mgr.update("server", "port", 9999)
    assert result["success"] is False
    assert result.get("restart_required") is True


def test_overrides_persist_to_file(tmp_data_dir: Path):
    """Overrides should be persisted to config_overrides.json."""
    mgr = RuntimeConfigManager()
    mgr.update("general", "log_level", "DEBUG")

    overrides_file = tmp_data_dir / "config_overrides.json"
    assert overrides_file.exists()

    with open(overrides_file) as f:
        data = json.load(f)
    assert data["general"]["log_level"] == "DEBUG"


def test_callbacks_fire_on_update(tmp_data_dir: Path):
    """Registered callbacks should fire when a setting is updated."""
    mgr = RuntimeConfigManager()
    received: list[tuple[str, object]] = []

    def on_change(key: str, value: object) -> None:
        received.append((key, value))

    mgr.register_callback("general", on_change)
    mgr.update("general", "timezone", "Europe/London")

    assert len(received) == 1
    assert received[0] == ("timezone", "Europe/London")


def test_env_takes_priority(tmp_data_dir: Path):
    """Environment variables should override both defaults and file overrides."""
    mgr = RuntimeConfigManager()
    mgr.update("general", "timezone", "US/Eastern")

    env_key = "MEMORY_MCP_TIMEZONE"
    os.environ[env_key] = "UTC"
    try:
        value, source = mgr.get_effective_value("general", "timezone")
        assert source == "env"
        assert value == "UTC"
    finally:
        del os.environ[env_key]


def test_singleton_pattern(tmp_data_dir: Path):
    """RuntimeConfigManager should return the same instance."""
    mgr1 = RuntimeConfigManager()
    mgr2 = RuntimeConfigManager()
    assert mgr1 is mgr2

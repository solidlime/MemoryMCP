"""Runtime configuration manager with hot-reload support."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable

from memory_mcp.config.settings import Settings, get_settings
from memory_mcp.infrastructure.logging.structured import get_logger

logger = get_logger(__name__)


# Settings metadata: which settings can be hot-reloaded
SETTINGS_META: dict[str, dict[str, dict]] = {
    "server": {
        "host": {"hot_reload": False, "description": "Server bind address"},
        "port": {"hot_reload": False, "description": "Server port"},
    },
    "embedding": {
        "model": {"hot_reload": True, "description": "Embedding model name", "reload_time": "10-60s"},
        "device": {"hot_reload": True, "description": "Device (cpu/cuda)", "reload_time": "10-60s"},
        "batch_size": {"hot_reload": True, "description": "Embedding batch size"},
    },
    "reranker": {
        "model": {"hot_reload": True, "description": "Reranker model name", "reload_time": "5-30s"},
        "enabled": {"hot_reload": True, "description": "Enable reranker"},
    },
    "qdrant": {
        "url": {"hot_reload": True, "description": "Qdrant server URL", "reload_time": "1-3s"},
        "api_key": {"hot_reload": True, "description": "Qdrant API key", "masked": True},
        "collection_prefix": {"hot_reload": True, "description": "Collection name prefix"},
    },
    "forgetting": {
        "enabled": {"hot_reload": True, "description": "Enable forgetting curve"},
        "decay_interval_seconds": {"hot_reload": True, "description": "Decay worker interval (seconds)"},
        "min_strength": {"hot_reload": True, "description": "Minimum memory strength"},
    },
    "general": {
        "timezone": {"hot_reload": True, "description": "Timezone"},
        "log_level": {"hot_reload": True, "description": "Log level"},
        "data_dir": {"hot_reload": False, "description": "Data directory"},
        "import_dir": {"hot_reload": True, "description": "Auto-import directory"},
        "default_persona": {"hot_reload": True, "description": "Default persona"},
        "contradiction_threshold": {"hot_reload": True, "description": "Contradiction detection threshold"},
        "duplicate_threshold": {"hot_reload": True, "description": "Duplicate detection threshold"},
    },
}


class ReloadStatus:
    """Track status of model/service reloads."""

    def __init__(self) -> None:
        self._statuses: dict[str, dict] = {}
        self._lock = threading.Lock()

    def set(self, key: str, status: str, progress: float | None = None, error: str | None = None) -> None:
        with self._lock:
            self._statuses[key] = {"status": status, "progress": progress, "error": error}

    def get(self, key: str) -> dict:
        with self._lock:
            return self._statuses.get(key, {"status": "ready", "progress": None, "error": None})

    def get_all(self) -> dict:
        with self._lock:
            return dict(self._statuses)


class RuntimeConfigManager:
    """Singleton manager for runtime configuration with hot-reload."""

    _instance: RuntimeConfigManager | None = None
    _lock = threading.Lock()

    def __new__(cls) -> RuntimeConfigManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._settings = get_settings()
        self._overrides: dict[str, Any] = {}
        self._callbacks: dict[str, list[Callable]] = {}
        self._reload_status = ReloadStatus()
        self._overrides_path = Path(self._settings.data_dir) / "config_overrides.json"
        self._load_overrides()

    def _load_overrides(self) -> None:
        """Load overrides from JSON file."""
        if self._overrides_path.exists():
            try:
                with open(self._overrides_path) as f:
                    self._overrides = json.load(f)
                logger.info("Loaded config overrides from %s", self._overrides_path)
            except Exception:
                logger.exception("Failed to load config overrides")
                self._overrides = {}

    def _save_overrides(self) -> None:
        """Persist overrides to JSON file."""
        self._overrides_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._overrides_path, "w") as f:
            json.dump(self._overrides, f, indent=2, ensure_ascii=False)
        logger.info("Saved config overrides to %s", self._overrides_path)

    def get_effective_value(self, category: str, key: str) -> tuple[Any, str]:
        """Get the effective value and its source for a setting.

        Returns: (value, source) where source is "env", "override", or "default"
        """
        # Check environment variable first
        env_key = self._get_env_key(category, key)
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return (env_val, "env")

        # Check overrides
        override_val = self._overrides.get(category, {}).get(key)
        if override_val is not None:
            return (override_val, "override")

        # Fall back to default from Settings
        return (self._get_settings_value(category, key), "default")

    def _get_env_key(self, category: str, key: str) -> str:
        """Construct environment variable name."""
        if category == "general":
            return f"MEMORY_MCP_{key.upper()}"
        return f"MEMORY_MCP_{category.upper()}__{key.upper()}"

    def _get_settings_value(self, category: str, key: str) -> Any:
        """Get value from current Settings instance."""
        if category == "general":
            return getattr(self._settings, key, None)
        sub = getattr(self._settings, category, None)
        if sub is not None:
            return getattr(sub, key, None)
        return None

    def get_all(self) -> dict:
        """Get all settings with metadata for the dashboard."""
        result: dict[str, dict] = {}
        for category, keys in SETTINGS_META.items():
            result[category] = {}
            for key, meta in keys.items():
                value, source = self.get_effective_value(category, key)
                entry = {
                    "value": "***" if meta.get("masked") and value else value,
                    "source": source,
                    **meta,
                }
                result[category][key] = entry
        return {
            "settings": result,
            "reload_status": self._reload_status.get_all(),
        }

    def update(self, category: str, key: str, value: Any) -> dict:
        """Update a setting. Returns status dict."""
        # Validate category/key
        if category not in SETTINGS_META or key not in SETTINGS_META[category]:
            return {"success": False, "error": f"Unknown setting: {category}.{key}"}

        meta = SETTINGS_META[category][key]
        if not meta.get("hot_reload", False):
            return {
                "success": False,
                "error": f"{category}.{key} requires server restart",
                "restart_required": True,
            }

        # Save override
        if category not in self._overrides:
            self._overrides[category] = {}
        self._overrides[category][key] = value
        self._save_overrides()

        # Apply to in-memory settings
        self._apply_setting(category, key, value)

        # Fire callbacks
        self._fire_callbacks(category, key, value)

        logger.info("Updated setting %s.%s = %s", category, key, value)
        return {"success": True, "category": category, "key": key, "value": value}

    def _apply_setting(self, category: str, key: str, value: Any) -> None:
        """Apply setting change to the in-memory Settings object."""
        if category == "general":
            setattr(self._settings, key, value)
        else:
            sub = getattr(self._settings, category, None)
            if sub is not None:
                setattr(sub, key, value)

    def register_callback(self, category: str, callback: Callable[[str, Any], None]) -> None:
        """Register a callback for when a setting in the given category changes.

        Callback receives (key, new_value).
        """
        if category not in self._callbacks:
            self._callbacks[category] = []
        self._callbacks[category].append(callback)

    def _fire_callbacks(self, category: str, key: str, value: Any) -> None:
        """Fire registered callbacks for the category."""
        for cb in self._callbacks.get(category, []):
            try:
                cb(key, value)
            except Exception:
                logger.exception("Callback failed for %s.%s", category, key)

    @property
    def reload_status(self) -> ReloadStatus:
        return self._reload_status

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._lock:
            cls._instance = None

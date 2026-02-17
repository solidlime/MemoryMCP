import json
import os
import threading
from copy import deepcopy
from typing import Any, Dict, Iterable, List

# BASE_DIR is src/utils/, so project root is two levels up
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG: Dict[str, Any] = {
    "embeddings_model": "cl-nagoya/ruri-v3-30m",
    "embeddings_device": "cpu",  # Unified device for all RAG models (embeddings, reranker, sentiment)
    "reranker_model": "hotchpotch/japanese-reranker-xsmall-v2",
    "reranker_top_n": 10,  # Increased from 5 for better quality (based on search quality tests)
    "sentiment_model": "cardiffnlp/twitter-xlm-roberta-base-sentiment",
    "server_host": "0.0.0.0",
    "server_port": 26262,
    "timezone": "Asia/Tokyo",
    "recent_memories_count": 5,  # Number of recent memories to show in get_context
    # Phase 25: Qdrant専用化（storage_backend削除、Qdrant必須）
    "qdrant_url": "http://localhost:6333",
    "qdrant_api_key": None,
    "qdrant_collection_prefix": "memory_",
    # Phase 28.4: 自己要約(メタメモリ)設定
    "summarization": {
        "enabled": True,
        "use_llm": False,  # True: LLM要約, False: 統計テンプレート要約
        "frequency_days": 1,  # 要約頻度(日数)
        "min_importance": 0.3,  # 要約対象の最小重要度
        "idle_minutes": 30,  # アイドル分数(自動要約トリガー)
        "check_interval_seconds": 3600,  # チェック間隔(秒)
        "llm_api_url": None,  # LLM API URL (OpenRouter: https://openrouter.ai/api/v1, OpenAI: https://api.openai.com/v1)
        "llm_api_key": None,  # LLM APIキー
        "llm_model": "anthropic/claude-3.5-sonnet",  # 使用モデル
        "llm_max_tokens": 500,  # 最大トークン数
        "llm_prompt": None,  # カスタム要約プロンプト(Noneなら内部デフォルト使用)
    },
    "vector_rebuild": {
        "mode": "idle",
        "idle_seconds": 30,
        "min_interval": 120,
    },
    "auto_cleanup": {
        "enabled": True,
        "idle_minutes": 30,
        "check_interval_seconds": 300,
        "duplicate_threshold": 0.90,
        "min_similarity_to_report": 0.85,
        "max_suggestions_per_run": 20,
    },
    # Progressive disclosure search settings (claude-mem inspired)
    "progressive_search": {
        "enabled": True,
        "keyword_first": True,        # Try keyword/tag search before semantic
        "keyword_threshold": 3,        # Min keyword hits before skipping semantic
        "semantic_fallback": True,     # Fall back to semantic if keyword yields <threshold
        "max_semantic_top_k": 5,       # Cap semantic results for resource saving
    },
    # Privacy filter settings
    "privacy": {
        "default_level": "internal",   # Default privacy for new memories
        "auto_redact_pii": False,      # Auto-redact PII patterns on save
        "search_max_level": "private", # Max privacy level returned in search
        "dashboard_max_level": "internal",  # Max level shown on dashboard
    },
    # Dashboard settings
    "dashboard": {
        "timeline_days": 14,           # Number of days for memory timeline chart
    },
    # DS920+ / low-resource host optimizations
    "resource_profile": "normal",      # "normal", "low" (DS920+), "minimal"
}

_ENV_PREFIX = "MEMORY_MCP_"
_RESERVED_ENV_KEYS = {
    f"{_ENV_PREFIX}DATA_DIR",
}

_config_cache: Dict[str, Any] = {}
_config_cache_lock = threading.Lock()
_config_cache_state = {
    "mtime": None,
    "env_signature": None,
}


def _deep_update(target: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            target[key] = _deep_update(target[key], value)
        else:
            target[key] = value
    return target


def _assign_nested(target: Dict[str, Any], keys: Iterable[str], value: Any) -> None:
    current = target
    *parents, leaf = list(keys)
    for key in parents:
        existing = current.get(key)
        if not isinstance(existing, dict):
            existing = {}
            current[key] = existing
        current = existing
    current[leaf] = value


def _parse_env_value(raw: str) -> Any:
    value = raw.strip()
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            continue
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError, ValueError):
        return value


def _load_env_overrides() -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for key, raw_value in os.environ.items():
        if not key.startswith(_ENV_PREFIX):
            continue
        if key in _RESERVED_ENV_KEYS:
            continue
        suffix = key[len(_ENV_PREFIX) :]
        if not suffix:
            continue
        lower = suffix.lower()
        value = _parse_env_value(raw_value)

        # Preferred explicit nesting with double underscore (e.g., VECTOR_REBUILD__MODE)
        if "__" in suffix:
            parts = [seg for seg in lower.split("__") if seg]
            if parts:
                _assign_nested(overrides, parts, value)
            continue

        # Friendly one-underscore mapping for known 2-level sections
        if lower.startswith("summarization_"):
            leaf = lower[len("summarization_") :]
            _assign_nested(overrides, ["summarization", leaf], value)
            continue
        if lower.startswith("vector_rebuild_"):
            leaf = lower[len("vector_rebuild_") :]
            _assign_nested(overrides, ["vector_rebuild", leaf], value)
            continue
        if lower.startswith("auto_cleanup_"):
            leaf = lower[len("auto_cleanup_") :]
            _assign_nested(overrides, ["auto_cleanup", leaf], value)
            continue

        # Fallback: treat as top-level key (e.g., SERVER_PORT)
        _assign_nested(overrides, [lower], value)
    return overrides


def get_config_path() -> str:
    """Get config file path (always DATA_DIR/config.json)"""
    data_dir = get_data_dir()
    return os.path.join(data_dir, "config.json")


def get_data_dir() -> str:
    """Get data directory path (default: data/)"""
    env_path = os.environ.get(f"{_ENV_PREFIX}DATA_DIR")
    if env_path:
        return os.path.abspath(env_path)
    # Default to ./data/ directory in project root
    return os.path.join(BASE_DIR, "data")


def get_memory_root() -> str:
    """Get memory data directory path"""
    return os.path.join(get_data_dir(), "memory")


def get_cache_dir() -> str:
    """Get cache directory path"""
    return os.path.join(get_data_dir(), "cache")


def get_logs_dir() -> str:
    """Get logs directory path"""
    return os.path.join(get_data_dir(), "logs")


def ensure_directory(path: str) -> str:
    if path:
        os.makedirs(path, exist_ok=True)
    return path


def ensure_memory_root() -> str:
    root = get_memory_root()
    ensure_directory(root)
    return root


def get_log_file_path() -> str:
    """Get log file path (always DATA_DIR/logs/memory_operations.log)"""
    logs_dir = get_logs_dir()
    ensure_directory(logs_dir)
    return os.path.join(logs_dir, "memory_operations.log")


def _load_file_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_config(force: bool = False) -> Dict[str, Any]:
    env_overrides = _load_env_overrides()
    env_signature = json.dumps(env_overrides, sort_keys=True, default=str)
    config_path = get_config_path()
    mtime = os.path.getmtime(config_path) if os.path.exists(config_path) else None

    with _config_cache_lock:
        cache_empty = not bool(_config_cache)
        cached_mtime = _config_cache_state.get("mtime")
        cached_env_signature = _config_cache_state.get("env_signature")
        if (
            force
            or cache_empty
            or cached_mtime != mtime
            or cached_env_signature != env_signature
        ):
            merged = deepcopy(DEFAULT_CONFIG)
            _deep_update(merged, env_overrides)
            file_config = _load_file_config(config_path)
            _deep_update(merged, file_config)
            # Special-case: allow env to override server_host/server_port even if config.json sets them
            # to make container port management easy without editing config files.
            if isinstance(env_overrides, dict):
                if "server_host" in env_overrides:
                    merged["server_host"] = env_overrides["server_host"]
                if "server_port" in env_overrides:
                    try:
                        merged["server_port"] = int(env_overrides["server_port"])  # ensure int
                    except Exception:
                        merged["server_port"] = env_overrides["server_port"]

            # Apply resource profile overrides (DS920+ / low-resource hosts)
            _apply_resource_profile(merged)

            _config_cache.clear()
            _config_cache.update(merged)
            _config_cache_state["mtime"] = mtime
            _config_cache_state["env_signature"] = env_signature
    return deepcopy(_config_cache)


# Resource profile presets for different hardware constraints
_RESOURCE_PROFILES: Dict[str, Dict[str, Any]] = {
    "low": {
        # DS920+ 20GB / NAS with decent RAM
        # CPU-constrained but memory-rich: allow better precision while staying lightweight
        "embeddings_device": "cpu",
        "reranker_top_n": 6,           # Relaxed from 3 (20GB allows larger candidate sets)
        "summarization": {
            "check_interval_seconds": 5400,   # 90min (relaxed from 120min)
            "idle_minutes": 45,                # Relaxed from 60min
        },
        "vector_rebuild": {
            "mode": "idle",
            "idle_seconds": 90,          # Relaxed from 120s
            "min_interval": 300,         # Relaxed from 600s
        },
        "auto_cleanup": {
            "check_interval_seconds": 450,
            "max_suggestions_per_run": 15,
        },
        "progressive_search": {
            "enabled": True,
            "keyword_first": True,
            "keyword_threshold": 2,
            "semantic_fallback": True,
            "max_semantic_top_k": 5,     # Relaxed from 3 (20GB headroom)
        },
        "dashboard": {
            "timeline_days": 14,          # Extended from 7
        },
    },
    "minimal": {
        # Very constrained environments (e.g., Raspberry Pi)
        "embeddings_device": "cpu",
        "reranker_model": "",  # Disable reranker
        "reranker_top_n": 0,
        "summarization": {
            "enabled": False,
        },
        "vector_rebuild": {
            "mode": "manual",
            "min_interval": 3600,
        },
        "auto_cleanup": {
            "enabled": False,
        },
        "progressive_search": {
            "enabled": True,
            "keyword_first": True,
            "keyword_threshold": 1,
            "semantic_fallback": False,
            "max_semantic_top_k": 2,
        },
    },
}


def _apply_resource_profile(config: Dict[str, Any]) -> None:
    """Apply resource profile presets to config if specified.

    Profile values are applied as defaults - explicit user settings take priority.
    """
    profile = config.get("resource_profile", "normal")
    if profile == "normal" or profile not in _RESOURCE_PROFILES:
        return

    preset = deepcopy(_RESOURCE_PROFILES[profile])
    # Only apply preset values where user hasn't explicitly set them
    # (i.e., where the current value still equals the DEFAULT_CONFIG value)
    _deep_update_defaults_only(config, preset, DEFAULT_CONFIG)


def _deep_update_defaults_only(
    target: Dict[str, Any],
    updates: Dict[str, Any],
    defaults: Dict[str, Any],
) -> None:
    """Apply updates only where target still has default values."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update_defaults_only(
                target[key], value, defaults.get(key, {}) if isinstance(defaults.get(key), dict) else {}
            )
        else:
            # Only override if current value is still the default
            if target.get(key) == defaults.get(key):
                target[key] = value


def get_config(key: str, default: Any = None) -> Any:
    config = load_config()
    return config.get(key, default)

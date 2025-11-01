import json
import os
import threading
from copy import deepcopy
from typing import Any, Dict, Iterable, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG: Dict[str, Any] = {
    "embeddings_model": "cl-nagoya/ruri-v3-30m",
    "embeddings_device": "cpu",
    "reranker_model": "hotchpotch/japanese-reranker-xsmall-v2",
    "reranker_top_n": 5,
    "server_host": "0.0.0.0",
    "server_port": 8000,
    "timezone": "Asia/Tokyo",
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
}

_ENV_PREFIX = "MEMORY_MCP_"
_RESERVED_ENV_KEYS = {
    f"{_ENV_PREFIX}CONFIG_PATH",
    f"{_ENV_PREFIX}DATA_DIR",
    f"{_ENV_PREFIX}LOG_FILE",
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
    env_path = os.environ.get(f"{_ENV_PREFIX}CONFIG_PATH")
    if env_path:
        return os.path.abspath(env_path)
    return os.path.join(BASE_DIR, "config.json")


def get_data_dir() -> str:
    """データディレクトリのルートパスを取得（memory/やlogs/の親ディレクトリ）"""
    env_path = os.environ.get(f"{_ENV_PREFIX}DATA_DIR")
    if env_path:
        return os.path.abspath(env_path)
    return BASE_DIR


def get_memory_root() -> str:
    """メモリデータディレクトリのパスを取得"""
    return os.path.join(get_data_dir(), "memory")


def get_cache_dir() -> str:
    """キャッシュディレクトリのパスを取得"""
    return os.path.join(get_data_dir(), "cache")


def get_logs_dir() -> str:
    """ログディレクトリのパスを取得"""
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
    env_path = os.environ.get(f"{_ENV_PREFIX}LOG_FILE")
    if env_path:
        path = os.path.abspath(env_path)
    else:
        logs_dir = get_logs_dir()
        ensure_directory(logs_dir)
        path = os.path.join(logs_dir, "memory_operations.log")
    ensure_directory(os.path.dirname(path) or BASE_DIR)
    return path


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
            _config_cache.clear()
            _config_cache.update(merged)
            _config_cache_state["mtime"] = mtime
            _config_cache_state["env_signature"] = env_signature
    return deepcopy(_config_cache)


def get_config(key: str, default: Any = None) -> Any:
    config = load_config()
    return config.get(key, default)
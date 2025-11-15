"""
Idle Summarization Worker for Memory MCP

Automatically generates memory summaries during idle periods.
Similar to vector_rebuild and auto_cleanup background tasks.
"""

import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from src.utils.config_utils import load_config
from src.utils.persona_utils import get_current_persona


# Globals for idle summarization
_last_write_ts: float = 0.0
_last_summarization_ts: float = 0.0
_summarization_lock = threading.Lock()


def _get_summarization_config():
    """Get summarization configuration from config.json"""
    cfg = load_config()
    s = cfg.get("summarization", {})
    return {
        "enabled": s.get("enabled", True),
        "idle_minutes": int(s.get("idle_minutes", 30)),
        "check_interval_seconds": int(s.get("check_interval_seconds", 3600)),  # 1 hour
        "frequency_days": int(s.get("frequency_days", 1)),
        "min_importance": float(s.get("min_importance", 0.3)),
    }


def mark_summarization_dirty():
    """Mark that a memory operation occurred (reset idle timer)"""
    global _last_write_ts
    _last_write_ts = time.time()


def start_summarization_worker_thread():
    """Start background summarization worker thread"""
    cfg = _get_summarization_config()
    if not cfg.get("enabled", True):
        print("📝 Auto-summarization disabled in config")
        return None
    
    print(f"📝 Starting auto-summarization worker (idle: {cfg['idle_minutes']}min, frequency: {cfg['frequency_days']}days)")
    t = threading.Thread(target=_summarization_worker_loop, daemon=True)
    t.start()
    return t


def _summarization_worker_loop():
    """Background loop that generates summaries during idle time"""
    global _last_summarization_ts, _last_write_ts
    
    while True:
        try:
            cfg = _get_summarization_config()
            if not cfg.get("enabled", True):
                time.sleep(60)
                continue
            
            now = time.time()
            check_interval = cfg.get("check_interval_seconds", 3600)
            
            # Wait for check interval
            if (now - _last_summarization_ts) < check_interval:
                time.sleep(60)
                continue
            
            # Check if idle (no writes for idle_minutes)
            idle_seconds = cfg.get("idle_minutes", 30) * 60
            if (now - _last_write_ts) < idle_seconds:
                time.sleep(60)
                continue
            
            # Check if it's time to summarize (based on frequency_days)
            frequency_seconds = cfg.get("frequency_days", 1) * 86400
            if (now - _last_summarization_ts) < frequency_seconds:
                time.sleep(60)
                continue
            
            # Run summarization
            with _summarization_lock:
                _last_summarization_ts = now
                _run_summarization(cfg)
            
            # Sleep after successful summarization
            time.sleep(check_interval)
            
        except Exception as e:
            print(f"⚠️ Summarization worker error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(300)  # 5 minutes on error


def _run_summarization(cfg):
    """Run summarization for current persona"""
    try:
        from tools.summarization_tools import summarize_last_day
        
        persona = get_current_persona()
        print(f"📝 Auto-summarization triggered for persona: {persona}")
        
        summary_key = summarize_last_day(persona=persona)
        
        if summary_key:
            print(f"✅ Auto-summary created: {summary_key}")
        else:
            print(f"⚠️ Auto-summarization skipped (no memories found)")
            
    except Exception as e:
        print(f"❌ Auto-summarization failed: {e}")
        import traceback
        traceback.print_exc()

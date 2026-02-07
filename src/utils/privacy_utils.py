"""
Privacy filter utilities for memory content.

Provides privacy_level assignment, PII detection, and content redaction
for memory storage and retrieval operations.

Privacy Levels:
    - "public": Safe for export/sharing
    - "internal": Default, visible within system only
    - "private": Excluded from search results and dashboard by default
    - "secret": Never returned in any search, dashboard, or export
"""

import re
from typing import Dict, List, Optional, Tuple

# Privacy level hierarchy (higher = more restricted)
PRIVACY_LEVELS = {
    "public": 0,
    "internal": 1,
    "private": 2,
    "secret": 3,
}

DEFAULT_PRIVACY_LEVEL = "internal"

# Simple PII patterns (lightweight, no ML needed - DS920+ friendly)
_PII_PATTERNS: List[Tuple[str, str]] = [
    # Email addresses
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),
    # Phone numbers (Japanese format)
    (r'\b0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}\b', '[PHONE]'),
    # IP addresses
    (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]'),
    # Credit card numbers (simple)
    (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CARD]'),
]

# Compiled patterns (compiled once for performance)
_COMPILED_PII = [(re.compile(p, re.IGNORECASE), r) for p, r in _PII_PATTERNS]


def detect_private_tags(content: str) -> bool:
    """
    Check if content contains <private> tags (claude-mem style).

    Args:
        content: Memory content to check

    Returns:
        True if content contains <private> tags
    """
    return bool(re.search(r'<private>.*?</private>', content, re.DOTALL))


def strip_private_tags(content: str) -> str:
    """
    Remove <private>...</private> tagged sections from content.

    Args:
        content: Memory content to filter

    Returns:
        Content with private-tagged sections removed
    """
    return re.sub(r'<private>.*?</private>', '', content, flags=re.DOTALL).strip()


def redact_pii(content: str) -> str:
    """
    Redact common PII patterns from content.
    Lightweight regex-based approach suitable for DS920+.

    Args:
        content: Content to redact

    Returns:
        Content with PII patterns replaced with placeholders
    """
    result = content
    for pattern, replacement in _COMPILED_PII:
        result = pattern.sub(replacement, result)
    return result


def determine_privacy_level(
    content: str,
    explicit_level: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> str:
    """
    Determine the privacy level for a memory entry.

    Priority:
    1. Explicit level if provided
    2. "secret" if content has <private> tags
    3. Tag-based detection (e.g., "private", "secret" tags)
    4. Default: "internal"

    Args:
        content: Memory content
        explicit_level: Explicitly set privacy level
        tags: Context tags for the memory

    Returns:
        Privacy level string
    """
    if explicit_level and explicit_level in PRIVACY_LEVELS:
        return explicit_level

    if detect_private_tags(content):
        return "secret"

    if tags:
        tag_lower = [t.lower() for t in tags]
        if "secret" in tag_lower:
            return "secret"
        if "private" in tag_lower:
            return "private"
        if "public" in tag_lower:
            return "public"

    return DEFAULT_PRIVACY_LEVEL


def filter_by_privacy(
    entries: List[Dict],
    max_level: str = "private",
    include_secret: bool = False,
) -> List[Dict]:
    """
    Filter memory entries by privacy level.

    Args:
        entries: List of memory entry dicts (must have 'privacy_level' key)
        max_level: Maximum privacy level to include
        include_secret: If True, include secret entries (admin mode)

    Returns:
        Filtered list of entries
    """
    max_rank = PRIVACY_LEVELS.get(max_level, 2)

    result = []
    for entry in entries:
        entry_level = entry.get("privacy_level", DEFAULT_PRIVACY_LEVEL)
        entry_rank = PRIVACY_LEVELS.get(entry_level, 1)

        if include_secret or entry_rank <= max_rank:
            result.append(entry)

    return result


def prepare_content_for_save(
    content: str,
    privacy_level: Optional[str] = None,
    auto_redact: bool = False,
    tags: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """
    Prepare memory content for saving with privacy handling.

    1. Determine privacy level
    2. Strip <private> tags if present
    3. Optionally redact PII

    Args:
        content: Raw memory content
        privacy_level: Explicit privacy level
        auto_redact: Whether to auto-redact PII
        tags: Context tags

    Returns:
        Tuple of (processed_content, determined_privacy_level)
    """
    level = determine_privacy_level(content, privacy_level, tags)

    # Strip private tags from stored content
    processed = strip_private_tags(content) if detect_private_tags(content) else content

    # Auto-redact PII if enabled
    if auto_redact:
        processed = redact_pii(processed)

    return processed, level

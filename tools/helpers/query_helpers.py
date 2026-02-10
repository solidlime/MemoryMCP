"""Query processing and expansion helpers."""

from typing import List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo


def is_ambiguous_query(query: str) -> bool:
    """
    Check if query is ambiguous and needs context expansion.

    Args:
        query: Search query string

    Returns:
        True if query appears ambiguous, False otherwise
    """
    if not query or len(query.strip()) < 5:
        return True

    q_lower = query.lower().strip()

    # Ambiguous phrases (Japanese)
    ambiguous_jp = [
        "いつものあれ", "いつもの", "あれ", "例の件", "あのこと",
        "あの件", "さっきの", "前の", "また"
    ]

    # Ambiguous phrases (English)
    ambiguous_en = [
        "that thing", "the usual", "you know", "that", "it",
        "the thing", "usual stuff", "same thing"
    ]

    for phrase in ambiguous_jp + ambiguous_en:
        if phrase in q_lower:
            return True

    return False


def build_expanded_query(
    query: Optional[str],
    now: datetime,
    search_tags: Optional[List[str]] = None
) -> tuple[str, Optional[List[str]]]:
    """
    Build expanded query with contextual information.

    Args:
        query: Original query string
        now: Current datetime
        search_tags: Existing search tags

    Returns:
        Tuple of (expanded_query, updated_search_tags)
    """
    # Check if query needs expansion
    needs_expansion = is_ambiguous_query(query or "")

    # Build expanded query with context
    expanded_parts = []
    if query:
        expanded_parts.append(query)

    # Only add time/day context for ambiguous queries
    if needs_expansion:
        # Add time context
        hour = now.hour
        if 6 <= hour < 12:
            expanded_parts.extend(["朝", "morning"])
        elif 12 <= hour < 18:
            expanded_parts.extend(["昼", "afternoon"])
        elif 18 <= hour < 22:
            expanded_parts.extend(["夜", "evening"])
        else:
            expanded_parts.extend(["深夜", "night"])

        # Add day context
        weekday = now.weekday()
        if weekday < 5:
            expanded_parts.extend(["平日", "weekday"])
        else:
            expanded_parts.extend(["週末", "weekend"])

    # Check for promise-related keywords
    updated_tags = search_tags.copy() if search_tags else []
    query_lower = (query or "").lower()
    if ("約束" in query_lower or "promise" in query_lower) and "promise" not in updated_tags:
        updated_tags.append("promise")

    # Use expanded query
    expanded_query = " ".join(expanded_parts) if expanded_parts else query or ""

    return expanded_query, updated_tags if updated_tags else None

"""MemoRAG ClueGenerator: LLM-based query clue generation."""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)

_CLUE_SYSTEM_PROMPT = """You are a memory search assistant. Given a summary of a person's memories and a search query, generate 3 specific search phrases that would help find relevant memories.

Rules:
- Output ONLY a JSON array of 3 short search phrases
- Each phrase should be 2-8 words
- Focus on specific details, people, events, emotions mentioned in the context
- Use the same language as the query (Japanese if query is in Japanese)
- Do NOT explain, just output the JSON array

Example output: ["フレーズ1", "specific phrase 2", "another phrase 3"]"""

_CLUE_USER_TEMPLATE = """Memory Context:
{context}

Search Query: {query}

Output 3 search phrases as a JSON array:"""


class ClueGenerator:
    """Generate search clue phrases using LLM for enhanced query expansion."""

    async def generate(
        self,
        context_snapshot_text: str,
        query: str,
        chat_config: ChatConfig,
    ) -> list[str]:
        """Generate clue phrases from context + query.

        Uses extract_model if set, falls back to main model.
        Returns empty list on failure (triggers smart fallback).
        """
        model = chat_config.extract_model or chat_config.get_effective_model()
        api_key = chat_config.get_effective_api_key()
        base_url = chat_config.get_effective_base_url()

        if not model or not api_key:
            logger.debug("ClueGenerator: no LLM configured, skipping clue generation")
            return []

        try:
            import httpx

            user_msg = _CLUE_USER_TEMPLATE.format(
                context=context_snapshot_text[:1500],
                query=query,
            )
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": _CLUE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 200,
                "temperature": 0.3,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                return _parse_clues(text)
        except Exception as e:
            logger.debug("ClueGenerator: LLM call failed: %s", e)
            return []


def _parse_clues(text: str) -> list[str]:
    """Extract up to 3 valid clue strings from LLM output."""
    text = text.strip()
    # Try to parse as JSON array
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(c).strip() for c in parsed if str(c).strip()][:3]
    except json.JSONDecodeError:
        pass
    # Fallback: extract quoted strings
    quoted = re.findall(r'"([^"]+)"', text)
    if quoted:
        return [q.strip() for q in quoted if q.strip()][:3]
    return []

"""Regex-based lightweight entity extraction. No LLM required."""

from __future__ import annotations

import re


class SimpleEntityExtractor:
    """Extract entity candidates from text using regular expressions.

    Designed for Japanese + mixed-language text.  Returns a de-duplicated
    list of ``(entity_name, entity_type)`` tuples.
    """

    # Katakana sequences (≥2 chars) — likely person / thing names
    KATAKANA_NAME = re.compile(r"[\u30A0-\u30FF]{2,}")

    # Place suffixes (CJK / Katakana prefix + known suffix)
    PLACE_SUFFIX = re.compile(
        r"[\u4e00-\u9fff\u30A0-\u30FF]{1,}"
        r"(?:駅|公園|ビル|タワー|城|寺|神社|大学|学校|病院|空港|港|山|川|湖|海|島|橋|通り|広場)"
    )

    # Common katakana stopwords to exclude
    _STOPWORDS: set[str] = frozenset({
        "メモリ", "コンテキスト", "エラー", "テスト", "データ",
        "ステータス", "タグ", "リスト", "ブロック", "アイテム",
        "カテゴリ", "システム", "サーバー", "クライアント",
        "コンテンツ", "メタデータ", "パラメータ",
    })

    def extract(self, text: str) -> list[tuple[str, str]]:
        """Return ``[(entity_name, entity_type), ...]`` from *text*.

        Entity types: ``person``, ``place``.
        """
        if not text:
            return []

        entities: list[tuple[str, str]] = []

        # 1. Places first (suffix match has higher precision)
        place_texts: set[str] = set()
        for match in self.PLACE_SUFFIX.finditer(text):
            name = match.group()
            place_texts.add(name)
            entities.append((name, "place"))

        # 2. Katakana names (likely persons, excluding places & stopwords)
        for match in self.KATAKANA_NAME.finditer(text):
            name = match.group()
            if name not in place_texts and name not in self._STOPWORDS and len(name) >= 2:
                entities.append((name, "person"))

        # De-duplicate while preserving first occurrence order
        seen: set[tuple[str, str]] = set()
        unique: list[tuple[str, str]] = []
        for pair in entities:
            if pair not in seen:
                seen.add(pair)
                unique.append(pair)
        return unique

"""LLM-free memory type classifier using regex heuristics.

Classifies memory content into 5 types:
  - decision   : choices made, trade-offs, architecture decisions
  - preference : personal rules, likes/dislikes, coding style
  - milestone  : breakthroughs, things that finally worked, shipped
  - problem    : bugs, errors, root causes, workarounds
  - emotional  : feelings, relationships, personal moments

Inspired by mempalace/general_extractor.py.
Supports English and Japanese.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Marker sets — one per memory type
# ---------------------------------------------------------------------------

_DECISION_EN = [
    r"\blet'?s (use|go with|try|pick|choose|switch to)\b",
    r"\bwe (should|decided|chose|went with|picked|settled on)\b",
    r"\bi'?m going (to|with)\b",
    r"\bbetter (to|than|approach|option|choice)\b",
    r"\binstead of\b",
    r"\brather than\b",
    r"\bthe reason (is|was|being)\b",
    r"\bbecause\b",
    r"\btrade-?off\b",
    r"\barchitecture\b",
    r"\bapproach\b",
    r"\bstrategy\b",
    r"\bpattern\b",
    r"\bframework\b",
    r"\bset (it |this )?to\b",
    r"\bconfigure\b",
    r"\bdefault\b",
]
_DECISION_JP = [
    r"にしました",
    r"決めた",
    r"採用",
    r"アーキテクチャ",
    r"方針",
    r"設計",
    r"なぜなら",
    r"だから",
    r"〜に変更",
    r"移行",
    r"トレードオフ",
    r"設定",
    r"デフォルト",
]

_PREFERENCE_EN = [
    r"\bi prefer\b",
    r"\balways use\b",
    r"\bnever use\b",
    r"\bdon'?t (ever |like to )?(use|do|mock|stub|import)\b",
    r"\bi like (to|when|how)\b",
    r"\bi hate (when|how|it when)\b",
    r"\bplease (always|never|don'?t)\b",
    r"\bmy (rule|preference|style|convention) is\b",
    r"\bwe (always|never)\b",
    r"\buse\b.*\binstead of\b",
]
_PREFERENCE_JP = [
    r"好き",
    r"嫌い",
    r"いつも",
    r"絶対に",
    r"使いたい",
    r"使いたくない",
    r"ルールは",
    r"スタイルは",
    r"推奨",
    r"非推奨",
    r"べき",
    r"すべき",
]

_MILESTONE_EN = [
    r"\bit works\b",
    r"\bit worked\b",
    r"\bgot it working\b",
    r"\bfixed\b",
    r"\bsolved\b",
    r"\bbreakthrough\b",
    r"\bfigured (it )?out\b",
    r"\bnailed it\b",
    r"\bfinally\b",
    r"\bfirst time\b",
    r"\bdiscovered\b",
    r"\brealized\b",
    r"\bturns out\b",
    r"\bthe key (is|was|insight)\b",
    r"\bthe trick (is|was)\b",
    r"\bnow i (understand|see|get it)\b",
    r"\bbuilt\b",
    r"\bimplemented\b",
    r"\bshipped\b",
    r"\blaunched\b",
    r"\bdeployed\b",
    r"\breleased\b",
    r"\bv\d+\.\d+",
    r"\d+% (reduction|improvement|faster|better)\b",
]
_MILESTONE_JP = [
    r"やっと",
    r"ついに",
    r"動いた",
    r"完成",
    r"リリース",
    r"解決した",
    r"できた",
    r"成功",
    r"実装完了",
    r"気づいた",
    r"分かった",
    r"理解した",
    r"なるほど",
    r"v\d+\.\d+",
    r"デプロイ",
    r"公開",
]

_PROBLEM_EN = [
    r"\b(bug|error|crash|fail|broke|broken|issue|problem)\b",
    r"\bdoesn'?t work\b",
    r"\bnot working\b",
    r"\bwon'?t\b.*\bwork\b",
    r"\bkeeps? (failing|crashing|breaking|erroring)\b",
    r"\broot cause\b",
    r"\bthe (problem|issue|bug) (is|was)\b",
    r"\bworkaround\b",
    r"\bthe fix (is|was)\b",
    r"\bsolution (is|was)\b",
    r"\bresolved\b",
]
_PROBLEM_JP = [
    r"バグ",
    r"エラー",
    r"壊れた",
    r"動かない",
    r"失敗",
    r"問題",
    r"不具合",
    r"原因",
    r"回避策",
    r"修正",
    r"直した",
    r"解決策",
]

_EMOTIONAL_EN = [
    r"\blove\b",
    r"\bscared\b",
    r"\bafraid\b",
    r"\bproud\b",
    r"\bhurt\b",
    r"\bhappy\b",
    r"\bsad\b",
    r"\bcrying\b",
    r"\bsorry\b",
    r"\bgrateful\b",
    r"\bangry\b",
    r"\bworried\b",
    r"\blonely\b",
    r"\bamazing\b",
    r"i feel",
    r"i'm scared",
    r"i love",
    r"i'm sorry",
    r"i wish",
    r"i miss",
    r"never told anyone",
]
_EMOTIONAL_JP = [
    r"嬉し",  # stem match — covers 嬉しい / 嬉しかった etc.
    r"悲しい",
    r"怖い",
    r"誇り",
    r"愛して",
    r"ごめん",
    r"感謝",
    r"怒り",
    r"心配",
    r"孤独",
    r"すごい",
    r"感動",
    r"感じる",
    r"気持ち",
]

_TYPE_MARKERS: dict[str, list[str]] = {
    "decision": _DECISION_EN + _DECISION_JP,
    "preference": _PREFERENCE_EN + _PREFERENCE_JP,
    "milestone": _MILESTONE_EN + _MILESTONE_JP,
    "problem": _PROBLEM_EN + _PROBLEM_JP,
    "emotional": _EMOTIONAL_EN + _EMOTIONAL_JP,
}

# Pre-compiled marker patterns for performance
_COMPILED_MARKERS: dict[str, list[re.Pattern[str]]] = {
    t: [re.compile(p, re.IGNORECASE) for p in markers] for t, markers in _TYPE_MARKERS.items()
}

# Type tags — used to skip auto-classification when already present
TYPE_TAGS: frozenset[str] = frozenset(_TYPE_MARKERS.keys())

# Confidence threshold — below this, no tag is added
_MIN_CONFIDENCE: float = 0.3

# ---------------------------------------------------------------------------
# Sentiment helpers for disambiguation
# ---------------------------------------------------------------------------

_POSITIVE_WORDS: frozenset[str] = frozenset(
    {
        "works",
        "working",
        "solved",
        "fixed",
        "nailed",
        "success",
        "breakthrough",
        "excited",
        "thrilled",
        "proud",
        "happy",
        "love",
        "great",
        "perfect",
        "動いた",
        "解決",
        "完成",
        "成功",
        "嬉しい",
        "すごい",
    }
)
_NEGATIVE_WORDS: frozenset[str] = frozenset(
    {
        "bug",
        "error",
        "crash",
        "fail",
        "failed",
        "failing",
        "broken",
        "broke",
        "issue",
        "problem",
        "wrong",
        "stuck",
        "blocked",
        "impossible",
        "バグ",
        "エラー",
        "壊れた",
        "失敗",
        "問題",
    }
)
_RESOLUTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bfixed\b",
        r"\bsolved\b",
        r"\bresolved\b",
        r"\bgot it working\b",
        r"\bit works\b",
        r"\bnailed it\b",
        r"\bfigured (it )?out\b",
        r"解決した",
        r"動いた",
        r"直した",
        r"できた",
    ]
]

# Code line patterns — skip these lines when scoring
_CODE_LINE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*[`]{3}"),
    re.compile(r"^\s*(import|from|def|class|function|const|let|var|return)\s"),
    re.compile(r"^\s*[$#]\s"),
    re.compile(r"^\s*(cd|source|echo|export|pip|npm|git|python|bash)\s"),
    re.compile(r"^\s*(if|for|while|try|except|elif|else:)\b"),
    re.compile(r"^\s*\w+\.\w+\("),
]


def _get_sentiment(text: str) -> str:
    words = set(re.findall(r"[\w\u3040-\u30FF\u4e00-\u9fff]+", text.lower()))
    pos = len(words & _POSITIVE_WORDS)
    neg = len(words & _NEGATIVE_WORDS)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _has_resolution(text: str) -> bool:
    return any(p.search(text) for p in _RESOLUTION_PATTERNS)


def _is_code_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    for pat in _CODE_LINE_PATTERNS:
        if pat.match(stripped):
            return True
    alpha_ratio = sum(1 for c in stripped if c.isalpha()) / max(len(stripped), 1)
    return alpha_ratio < 0.35 and len(stripped) > 10


def _extract_prose(text: str) -> str:
    """Remove code blocks and code lines; return prose only."""
    lines = text.split("\n")
    prose: list[str] = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or _is_code_line(line):
            continue
        prose.append(line)
    result = "\n".join(prose).strip()
    return result if result else text


def _score(text: str, patterns: list[re.Pattern[str]]) -> float:
    text_lower = text.lower()
    return sum(len(p.findall(text_lower)) for p in patterns)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify(content: str, min_confidence: float = _MIN_CONFIDENCE) -> str | None:
    """Classify memory content into one of 5 types.

    Returns a type string (``"decision"``, ``"preference"``, ``"milestone"``,
    ``"problem"``, or ``"emotional"``) or ``None`` if confidence is too low.

    Args:
        content: The memory text to classify.
        min_confidence: Minimum confidence (0–1). Defaults to 0.3.
    """
    prose = _extract_prose(content)
    if len(prose.strip()) < 10:
        return None

    scores: dict[str, float] = {}
    for type_name, patterns in _COMPILED_MARKERS.items():
        s = _score(prose, patterns)
        if s > 0:
            scores[type_name] = s

    if not scores:
        return None

    # Length bonus for longer content
    length_bonus = 2 if len(prose) > 500 else (1 if len(prose) > 200 else 0)
    best_type = max(scores, key=lambda t: scores[t])
    best_score = scores[best_type] + length_bonus

    # Disambiguation: resolved problem → milestone
    if best_type == "problem":
        if _has_resolution(prose):
            sentiment = _get_sentiment(prose)
            best_type = "emotional" if scores.get("emotional", 0) > 0 and sentiment == "positive" else "milestone"
        elif _get_sentiment(prose) == "positive":
            if scores.get("milestone", 0) > 0:
                best_type = "milestone"
            elif scores.get("emotional", 0) > 0:
                best_type = "emotional"

    confidence = min(1.0, best_score / 3.0)
    if confidence < min_confidence:
        return None

    return best_type


def auto_tags(content: str, existing_tags: list[str] | None = None) -> list[str]:
    """Return auto-generated type tags for *content*.

    Returns an empty list if:
    - confidence is too low
    - *existing_tags* already contains a type tag

    The returned list contains at most one element (the detected type).
    """
    tags = existing_tags or []
    if any(t in TYPE_TAGS for t in tags):
        return []

    detected = classify(content)
    if detected is None:
        return []
    return [detected]

"""Unit tests for memory type_classifier."""

from __future__ import annotations

from memory_mcp.domain.memory.type_classifier import TYPE_TAGS, auto_tags, classify

# ---------------------------------------------------------------------------
# classify() — English
# ---------------------------------------------------------------------------


class TestClassifyEnglish:
    def test_decision_basic(self):
        assert classify("We decided to use PostgreSQL because it's more reliable") == "decision"

    def test_decision_architecture(self):
        assert classify("The architecture uses a layered approach with a domain service") == "decision"

    def test_preference_always(self):
        assert classify("Always use snake_case for Python variables") == "preference"

    def test_preference_never(self):
        assert classify("Never use mocks in integration tests") == "preference"

    def test_milestone_it_works(self):
        assert classify("It works! Finally got the embedding model to load correctly") == "milestone"

    def test_milestone_shipped(self):
        assert classify("Shipped v1.2 to production, deployed successfully") == "milestone"

    def test_problem_bug(self):
        # Unresolved bug should stay as problem
        assert classify("There is a bug in the search engine that keeps crashing") == "problem"

    def test_emotional_love(self):
        assert classify("I love working on this project, it makes me happy") == "emotional"

    def test_emotional_i_feel(self):
        assert classify("I feel proud of what we built together") == "emotional"


# ---------------------------------------------------------------------------
# classify() — Japanese
# ---------------------------------------------------------------------------


class TestClassifyJapanese:
    def test_decision_jp(self):
        result = classify("検索アーキテクチャをhybrid+RRFにしました。なぜならパフォーマンスが良いからです")
        assert result == "decision"

    def test_preference_jp(self):
        result = classify("Pythonではいつもスネークケースを使う。キャメルケースは絶対に使わない")
        assert result == "preference"

    def test_milestone_jp(self):
        result = classify("やっと動いた！CIが全グリーンになって完成しました")
        assert result == "milestone"

    def test_problem_jp(self):
        result = classify("バグが発生している。SQLiteでエラーが出て動かない")
        assert result == "problem"

    def test_emotional_jp(self):
        # 嬉し (stem) × 1, 感動 × 1, 気持ち × 1 → emotional wins clearly
        result = classify("完成したとき本当に嬉しかった。感動して気持ちが溢れた")
        assert result == "emotional"


# ---------------------------------------------------------------------------
# Disambiguation
# ---------------------------------------------------------------------------


class TestDisambiguation:
    def test_resolved_problem_becomes_milestone(self):
        result = classify("There was a bug in the auth module, but I fixed it and now it works")
        assert result == "milestone"

    def test_resolved_problem_jp_becomes_milestone(self):
        result = classify("バグがあったけど解決した。やっと動いた")
        assert result == "milestone"

    def test_unresolved_problem_stays(self):
        result = classify("The server keeps crashing every 10 minutes, can't figure out why")
        assert result == "problem"


# ---------------------------------------------------------------------------
# Code line filtering
# ---------------------------------------------------------------------------


class TestCodeFiltering:
    def test_pure_code_block_returns_none(self):
        code = "```python\nimport os\ndef foo():\n    return 42\n```"
        # Pure code with no prose → low confidence or None
        result = classify(code)
        # Should not classify as anything meaningful
        assert result in (None, "decision", "preference", "milestone", "problem", "emotional")

    def test_mixed_code_and_prose_milestone(self):
        content = (
            "Finally got it working!\n"
            "```python\ndef embed(text):\n    return model.encode(text)\n```\n"
            "The trick was to normalize the vectors before computing cosine similarity."
        )
        assert classify(content) == "milestone"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_string_returns_none(self):
        assert classify("") is None

    def test_very_short_content_returns_none(self):
        assert classify("hi") is None

    def test_low_confidence_returns_none(self):
        # Completely neutral content with no markers
        assert classify("The sky is blue today and the weather is nice") is None

    def test_type_tags_constant(self):
        assert frozenset({"decision", "preference", "milestone", "problem", "emotional"}) == TYPE_TAGS


# ---------------------------------------------------------------------------
# auto_tags()
# ---------------------------------------------------------------------------


class TestAutoTags:
    def test_adds_tag_when_none_present(self):
        tags = auto_tags("We decided to use Redis because it's fast", existing_tags=[])
        assert tags == ["decision"]

    def test_skips_when_type_tag_present(self):
        tags = auto_tags("We decided to use Redis", existing_tags=["decision"])
        assert tags == []

    def test_skips_any_type_tag(self):
        for t in TYPE_TAGS:
            tags = auto_tags("We decided to use Redis", existing_tags=[t])
            assert tags == [], f"Should skip when '{t}' tag is already present"

    def test_returns_empty_on_low_confidence(self):
        tags = auto_tags("The sky is blue today")
        assert tags == []

    def test_preserves_non_type_tags(self):
        tags = auto_tags("Finally fixed the bug, it works now!", existing_tags=["important", "project-x"])
        # Should return milestone, non-type tags not affected
        assert tags == ["milestone"]

    def test_none_existing_tags(self):
        tags = auto_tags("Always use black for code formatting", existing_tags=None)
        assert tags == ["preference"]

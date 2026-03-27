from __future__ import annotations

from unittest.mock import MagicMock


class TestBoostRecall:
    def test_boost_recall_updates_strength(self) -> None:
        """boost_recall() が呼ばれると strength が更新される"""
        from memory_mcp.domain.memory.entities import MemoryStrength

        repo = MagicMock()
        existing_strength = MemoryStrength(memory_key="mem_001")
        repo.get_strength.return_value = MagicMock(is_ok=True, value=existing_strength)
        repo.save_strength.return_value = MagicMock(is_ok=True)

        from memory_mcp.domain.memory.service import MemoryService

        service = MemoryService(repo)
        result = service.boost_recall("mem_001")

        assert result.is_ok
        repo.save_strength.assert_called_once()

    def test_boost_recall_creates_new_strength_if_not_exists(self) -> None:
        """strength が存在しない場合は新規作成する"""
        repo = MagicMock()
        repo.get_strength.return_value = MagicMock(is_ok=True, value=None)
        repo.save_strength.return_value = MagicMock(is_ok=True)

        from memory_mcp.domain.memory.service import MemoryService

        service = MemoryService(repo)
        result = service.boost_recall("mem_new")

        assert result.is_ok
        repo.save_strength.assert_called_once()

    def test_boost_recall_returns_failure_on_repo_error(self) -> None:
        """リポジトリエラー時は Failure を返す"""
        repo = MagicMock()
        repo.get_strength.return_value = MagicMock(is_ok=False, error="DB error")

        from memory_mcp.domain.memory.service import MemoryService

        service = MemoryService(repo)
        result = service.boost_recall("mem_fail")

        assert not result.is_ok

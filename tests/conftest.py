import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@pytest.fixture
def tmp_db(tmp_path):
    """一時SQLiteデータベース"""
    db_path = tmp_path / "test_memory.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant client"""
    client = MagicMock()
    client.get_collections = MagicMock(return_value=MagicMock(collections=[]))
    client.create_collection = MagicMock()
    client.upsert = MagicMock()
    client.search = MagicMock(return_value=[])
    client.delete = MagicMock()
    client.count = MagicMock(return_value=MagicMock(count=0))
    return client


@pytest.fixture
def test_persona():
    """テスト用Persona名"""
    return "test_persona"


@pytest.fixture
def sample_memory_data():
    """テスト用サンプルメモリデータ"""
    return {
        "content": "テスト用の記憶データです。ユーザーはラーメンが好き。",
        "importance": 0.7,
        "emotion_type": "joy",
        "emotion_intensity": 0.8,
        "context_tags": ["food", "preference"],
    }


@pytest.fixture
def sample_item_data():
    """テスト用サンプルアイテムデータ"""
    return {
        "item_name": "白いドレス",
        "category": "clothing",
        "description": "シンプルな白いドレス",
    }


@pytest.fixture
def zip_paths():
    """旧データzipファイルへのパス"""
    return {
        "herta": DATA_DIR / "herta.zip",
        "nilou": DATA_DIR / "nilou.zip",
        "citlali": DATA_DIR / "citlali.zip",
    }


@pytest.fixture
def legacy_data_dir():
    """旧データの展開先ディレクトリ"""
    return DATA_DIR / "_tmp"

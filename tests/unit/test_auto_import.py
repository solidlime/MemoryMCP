"""Tests for auto-import functionality."""

from __future__ import annotations

import contextlib
import logging
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from memory_mcp.application.auto_import import run_auto_import
from memory_mcp.config.settings import Settings

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _zip_available(*names: str) -> bool:
    """Check if test data zip files are available."""
    return all((DATA_DIR / f"{n}.zip").exists() for n in names)


@pytest.fixture
def import_settings(tmp_path):
    """Create Settings with temporary directories for auto-import tests."""
    from memory_mcp.application.use_cases import AppContextRegistry

    import_dir = tmp_path / "import"
    import_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    settings = Settings()
    settings.data_dir = str(data_dir)
    settings.import_dir = str(import_dir)

    AppContextRegistry.configure(settings)
    return settings


@pytest.fixture(autouse=True)
def _isolate_test(monkeypatch):
    """Isolate each test: mock vector_store property and clean up registry."""
    from memory_mcp.application.use_cases import AppContext, AppContextRegistry

    monkeypatch.setattr(AppContext, "vector_store", property(lambda self: None))

    yield

    with contextlib.suppress(Exception):
        AppContextRegistry.close_all()
    AppContextRegistry._contexts.clear()
    AppContextRegistry._settings = None


def test_disabled_when_import_dir_empty(tmp_path):
    """import_dir が空なら即 {} を返し、LegacyImporter は呼ばれない。"""
    mock_importer_cls = MagicMock()

    settings = Settings()
    settings.import_dir = ""
    settings.data_dir = str(tmp_path)

    from unittest.mock import patch

    with patch("memory_mcp.application.auto_import.LegacyImporter", mock_importer_cls):
        result = run_auto_import(settings)

    assert result == {}
    mock_importer_cls.assert_not_called()


def test_creates_import_dir_if_not_exists(tmp_path):
    """存在しないディレクトリを指定 → 作成されて {} を返す。"""
    non_existent = tmp_path / "does_not_exist"

    settings = Settings()
    settings.data_dir = str(tmp_path)
    settings.import_dir = str(non_existent)

    result = run_auto_import(settings)

    assert non_existent.exists()
    assert non_existent.is_dir()
    assert result == {}


def test_empty_directory_returns_empty(import_settings):
    """空のインポートディレクトリ → {} を返す。"""
    result = run_auto_import(import_settings)
    assert result == {}


@pytest.mark.skipif(not _zip_available("herta"), reason="herta.zip not found")
def test_imports_single_zip(import_settings):
    """単一zipインポート: herta.zip → memories=165, done/に移動。"""
    import_dir = Path(import_settings.import_dir)
    shutil.copy2(DATA_DIR / "herta.zip", import_dir / "herta.zip")

    result = run_auto_import(import_settings)

    assert "herta" in result
    assert result["herta"]["memories"] == 165
    assert (import_dir / "done" / "herta.zip").exists()
    assert not (import_dir / "herta.zip").exists()


@pytest.mark.skipif(
    not _zip_available("herta", "nilou", "citlali"),
    reason="Test data zips not found",
)
def test_imports_multiple_zips(import_settings):
    """複数zipインポート: 3ペルソナ全てが正しくインポートされる。"""
    import_dir = Path(import_settings.import_dir)
    expected = {"herta": 165, "nilou": 1210, "citlali": 411}

    for name in expected:
        shutil.copy2(DATA_DIR / f"{name}.zip", import_dir / f"{name}.zip")

    result = run_auto_import(import_settings)

    for name, count in expected.items():
        assert name in result, f"{name} not in result"
        assert result[name]["memories"] == count
        assert (import_dir / "done" / f"{name}.zip").exists()


@pytest.mark.skipif(not _zip_available("herta"), reason="herta.zip not found")
def test_overwrites_existing_data(import_settings):
    """同じzipを2回インポート → メモリ数が重複しない (INSERT OR REPLACE)。"""
    import_dir = Path(import_settings.import_dir)

    # 1st import
    shutil.copy2(DATA_DIR / "herta.zip", import_dir / "herta.zip")
    result1 = run_auto_import(import_settings)
    assert result1["herta"]["memories"] == 165

    # Move zip back from done/ for 2nd import
    shutil.move(
        str(import_dir / "done" / "herta.zip"),
        str(import_dir / "herta.zip"),
    )
    result2 = run_auto_import(import_settings)
    assert result2["herta"]["memories"] == 165

    # Verify actual row count in DB — no duplicates
    from memory_mcp.infrastructure.sqlite.connection import SQLiteConnection

    conn = SQLiteConnection(import_settings.data_dir, "herta")
    try:
        row = conn.get_memory_db().execute("SELECT COUNT(*) FROM memories").fetchone()
        assert row[0] == 165
    finally:
        conn.close()


@pytest.mark.skipif(not _zip_available("herta"), reason="herta.zip not found")
def test_moves_zip_to_done(import_settings):
    """インポート後、zipが元のパスから消え done/ に存在する。"""
    import_dir = Path(import_settings.import_dir)
    shutil.copy2(DATA_DIR / "herta.zip", import_dir / "herta.zip")

    run_auto_import(import_settings)

    assert not (import_dir / "herta.zip").exists()
    assert (import_dir / "done" / "herta.zip").exists()


@pytest.mark.skipif(not _zip_available("herta"), reason="herta.zip not found")
def test_vector_sync_skipped_when_qdrant_unavailable(import_settings, caplog):
    """Qdrant不可でもSQLiteインポートは成功し、ログに 'Qdrant unavailable' が出る。"""
    import_dir = Path(import_settings.import_dir)
    shutil.copy2(DATA_DIR / "herta.zip", import_dir / "herta.zip")

    with caplog.at_level(logging.INFO):
        result = run_auto_import(import_settings)

    assert "herta" in result
    assert result["herta"]["memories"] == 165
    assert any("Qdrant unavailable" in msg for msg in caplog.messages)


@pytest.mark.skipif(not _zip_available("herta"), reason="herta.zip not found")
def test_invalid_zip_skipped(import_settings):
    """壊れたzipはスキップされ、有効なzipは正常にインポートされる。"""
    import_dir = Path(import_settings.import_dir)

    # Create an invalid zip (text file renamed to .zip)
    bad_zip = import_dir / "broken.zip"
    bad_zip.write_text("this is not a zip file", encoding="utf-8")

    # Also copy a valid zip
    shutil.copy2(DATA_DIR / "herta.zip", import_dir / "herta.zip")

    result = run_auto_import(import_settings)

    assert "broken" not in result
    assert "herta" in result
    assert result["herta"]["memories"] == 165


@pytest.mark.skipif(not _zip_available("herta"), reason="herta.zip not found")
def test_persona_name_from_filename(import_settings):
    """ファイル名 my-persona.zip → ペルソナ名 'my-persona' になる。"""
    import_dir = Path(import_settings.import_dir)
    shutil.copy2(DATA_DIR / "herta.zip", import_dir / "my-persona.zip")

    result = run_auto_import(import_settings)

    assert "my-persona" in result
    assert "herta" not in result

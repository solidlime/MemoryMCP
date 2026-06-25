"""
PDF解析ツール (_handle_read_pdf) の単体テスト

テスト対象: memory_mcp.application.chat.tools.builtin._handle_read_pdf
シグネチャ: async def _handle_read_pdf(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict

テスト用PDFは PyMuPDF (fitz) で動的に生成し、テスト後に確実に削除する。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import fitz  # PyMuPDF
import pytest

# ── ヘルパー ──


def create_test_pdf(path: str) -> str:
    """テスト用PDFを作成 (1ページ、テキスト+図形を含む)

    日本語テキストを正しく抽出できるよう fontname='japan' を指定する。
    """
    doc = fitz.open()
    page = doc.new_page()

    # テキスト挿入 (CJKフォントを指定して日本語を正しく埋め込む)
    page.insert_text((50, 50), "テスト用PDF文書", fontname="japan")
    page.insert_text((50, 80), "これはテスト文書です。", fontname="japan")
    page.insert_text((50, 110), "サンプルテキスト行3", fontname="japan")

    # 簡単な矩形を描画 (画像として抽出されるわけではないがxobjectとして埋め込まれる)
    rect = fitz.Rect(100, 200, 200, 250)
    page.draw_rect(rect, color=(0, 0, 1), fill=(0.5, 0.5, 0.5))

    doc.save(path)
    doc.close()
    return path


def create_test_pdf_multi_page(path: str, pages: int = 3) -> str:
    """複数ページのテストPDFを作成"""
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((50, 50), f"ページ {i + 1}", fontname="japan")
        page.insert_text((50, 80), f"内容 {i + 1}", fontname="japan")
    doc.save(path)
    doc.close()
    return path


# ── テスト ──


@pytest.mark.asyncio
async def test_read_pdf_basic_text():
    """PDFテキスト抽出の基本テスト"""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = create_test_pdf(f.name)

    try:
        ctx = MagicMock()
        config = MagicMock()

        from memory_mcp.application.chat.tools.builtin import _handle_read_pdf

        result = await _handle_read_pdf(ctx, config, {"path": pdf_path})

        assert result["status"] == "success"
        assert "テスト用PDF文書" in result["text"]
        assert "サンプルテキスト行3" in result["text"]
        assert result["pages"] == 1
        assert result["filename"].endswith(".pdf")
    finally:
        Path(pdf_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_pdf_multi_page():
    """複数ページPDF"""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = create_test_pdf_multi_page(f.name, pages=3)

    try:
        ctx = MagicMock()
        config = MagicMock()

        from memory_mcp.application.chat.tools.builtin import _handle_read_pdf

        result = await _handle_read_pdf(ctx, config, {"path": pdf_path})

        assert result["status"] == "success"
        assert result["pages"] == 3
        assert "ページ 1" in result["text"]
        assert "ページ 2" in result["text"]
        assert "ページ 3" in result["text"]
    finally:
        Path(pdf_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_pdf_file_not_found():
    """存在しないファイルのエラーハンドリング"""
    ctx = MagicMock()
    config = MagicMock()

    from memory_mcp.application.chat.tools.builtin import _handle_read_pdf

    result = await _handle_read_pdf(ctx, config, {"path": "/tmp/nonexistent_file_xyz.pdf"})

    assert result["status"] == "error"
    assert "ファイルが見つかりません" in result["message"]


@pytest.mark.asyncio
async def test_read_pdf_not_a_pdf():
    """PDF以外のファイルはエラー"""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"not a pdf")
        txt_path = f.name

    try:
        ctx = MagicMock()
        config = MagicMock()

        from memory_mcp.application.chat.tools.builtin import _handle_read_pdf

        result = await _handle_read_pdf(ctx, config, {"path": txt_path})

        assert result["status"] == "error"
        assert "PDFファイルではありません" in result["message"]
    finally:
        Path(txt_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_pdf_missing_path():
    """pathパラメータ不足"""
    ctx = MagicMock()
    config = MagicMock()

    from memory_mcp.application.chat.tools.builtin import _handle_read_pdf

    result = await _handle_read_pdf(ctx, config, {})

    assert result["status"] == "error"
    assert "パス" in result["message"]


@pytest.mark.asyncio
async def test_read_pdf_has_tables():
    """tables / images フィールドが常に返されること"""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = create_test_pdf(f.name)

    try:
        ctx = MagicMock()
        config = MagicMock()

        from memory_mcp.application.chat.tools.builtin import _handle_read_pdf

        result = await _handle_read_pdf(ctx, config, {"path": pdf_path})

        assert result["status"] == "success"
        # tables フィールドがリストであること
        assert "tables" in result
        assert isinstance(result["tables"], list)
        # images フィールドがリストであること
        assert "images" in result
        assert isinstance(result["images"], list)
    finally:
        Path(pdf_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_pdf_text_truncation():
    """長文テキストが100,000文字で切り詰められること

    複数ページにまたがる大量テキストで、テキスト上限 (100,000文字)
    を超えた場合に切り捨てメッセージが付与されることを確認する。
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    # 100K文字を超えるテキストを含むPDFを生成 (ASCIIテキストで十分)
    doc = fitz.open()
    line = "Lorem ipsum dolor sit amet consectetur adipiscing elit. " * 8
    pages_needed = 100  # 100ページあれば 100K を超える
    for i in range(pages_needed):
        page = doc.new_page()
        for j in range(10):
            page.insert_text((50, 50 + j * 15), f"P{i:03d} {line}", fontsize=5)
    doc.save(pdf_path)
    doc.close()

    try:
        ctx = MagicMock()
        config = MagicMock()

        from memory_mcp.application.chat.tools.builtin import _handle_read_pdf

        result = await _handle_read_pdf(ctx, config, {"path": pdf_path})

        assert result["status"] == "success"
        # テキストが上限 (100,000) + 切り捨てメッセージ分に収まっている
        assert len(result["text"]) <= 100_100
        assert "切り捨てられました" in result["text"]
    finally:
        Path(pdf_path).unlink(missing_ok=True)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Common - Shared utilities for MCP client scripts

Provides common functionality for all MCP client scripts:
- Configuration loading
- MCP tool invocation
- Output formatting
- Console encoding setup
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
import requests

# 環境変数でPythonのI/OエンコーディングをUTF-8に強制
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform == "win32":
    os.environ['PYTHONUTF8'] = '1'

# コンソール出力のエンコーディングをUTF-8に設定（Windows対応）
if sys.platform == "win32":
    import io
    import ctypes

    # Windows APIでコンソールをUTF-8モードに設定
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass

    # stdout/stderr を UTF-8 で再ラップ
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True,
            write_through=True
        )
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True,
            write_through=True
        )
else:
    import io
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True
        )
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True
        )


def load_config() -> Dict[str, Any]:
    """Load configuration file"""
    config_path = Path(__file__).parent.parent / "references" / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def call_mcp_tool(
    tool_name: str,
    params: Dict[str, Any],
    persona: str,
    server_url: str
) -> Dict[str, Any]:
    """
    MCPツールを呼び出す

    Args:
        tool_name: ツール名（get_context, memory, item）
        params: ツールパラメータ
        persona: ペルソナ名
        server_url: MCPサーバーURL

    Returns:
        レスポンスJSON
    """
    url = f"{server_url}/mcp/v1/tools/{tool_name}"
    headers = {
        "Authorization": f"Bearer {persona}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "success": False}


def format_output(data: Dict[str, Any], output_format: str = "text") -> str:
    """
    出力をフォーマット

    Args:
        data: 出力データ
        output_format: 出力形式（json|text）

    Returns:
        フォーマットされた文字列
    """
    output = []
    output.append("=" * 60)

    if output_format == "json":
        output.append(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        # テキスト形式
        if "error" in data:
            output.append(f"❌ エラー: {data['error']}")
        elif "result" in data:
            output.append(data["result"])
        else:
            output.append(json.dumps(data, ensure_ascii=False, indent=2))

    output.append("=" * 60)
    return "\n".join(output)


def get_config_defaults(config: Dict[str, Any]) -> tuple[str, str]:
    """
    設定のデフォルト値を取得

    Args:
        config: 設定辞書

    Returns:
        (persona, server_url)
    """
    persona = config.get("persona", {}).get("default", "default")
    server_url = config.get("mcp_server", {}).get("url", "http://localhost:26262")
    return persona, server_url

#!/usr/bin/env python3
"""
Context Status - Get Current Persona Context

このスクリプトはMemory MCPサーバーからget_context()を呼び出し、
現在のペルソナの状態、時刻、メモリ統計を取得します。

使用方法:
    python get_context.py [--persona PERSONA_NAME] [--url SERVER_URL]

引数:
    --persona    ペルソナ名（デフォルト: nilou）
    --url        MCPサーバーURL（デフォルト: http://localhost:3000）
    --format     出力形式 (json|text)（デフォルト: text）
"""

import argparse
import json
import sys
from pathlib import Path
import requests


def load_config():
    """設定ファイルを読み込む"""
    config_path = Path(__file__).parent.parent / "references" / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def get_context(persona: str = "nilou", server_url: str = "http://localhost:26262"):
    """
    Memory MCPサーバーからコンテキストを取得

    Args:
        persona: ペルソナ名
        server_url: MCPサーバーのURL

    Returns:
        dict: コンテキスト情報
    """
    url = f"{server_url}/mcp/v1/tools/get_context"
    headers = {
        "Authorization": f"Bearer {persona}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json={}, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def format_output(context_data: dict, output_format: str = "text") -> str:
    """
    コンテキストデータを整形

    Args:
        context_data: コンテキストデータ
        output_format: 出力形式（json or text）

    Returns:
        str: 整形された文字列
    """
    if output_format == "json":
        return json.dumps(context_data, ensure_ascii=False, indent=2)

    if "error" in context_data:
        return f"❌ エラー: {context_data['error']}"

    # テキスト形式で整形
    output = []
    output.append("=" * 60)
    output.append("📊 Context Status")
    output.append("=" * 60)

    if "content" in context_data:
        content = context_data["content"]
        if isinstance(content, list) and len(content) > 0:
            text_content = content[0].get("text", "")
            output.append(text_content)
        else:
            output.append(str(content))
    else:
        output.append(json.dumps(context_data, ensure_ascii=False, indent=2))

    output.append("=" * 60)
    return "\n".join(output)


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="Memory MCPサーバーからコンテキストを取得"
    )
    parser.add_argument(
        "--persona",
        default="nilou",
        help="ペルソナ名（デフォルト: nilou）"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:26262",
        help="MCPサーバーURL（デフォルト: http://localhost:26262）"
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="出力形式（デフォルト: text）"
    )

    args = parser.parse_args()

    # 設定ファイルから読み込み（コマンドライン引数が優先）
    config = load_config()
    if not args.url and config.get("mcp_server", {}).get("url"):
        args.url = config["mcp_server"]["url"]
    if not args.persona and config.get("persona", {}).get("default"):
        args.persona = config["persona"]["default"]

    # コンテキスト取得
    context_data = get_context(args.persona, args.url)

    # 結果を出力
    output = format_output(context_data, args.format)
    print(output)

    # エラーがあれば終了コード1
    if "error" in context_data:
        sys.exit(1)


if __name__ == "__main__":
    main()

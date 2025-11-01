#!/usr/bin/env python3
"""
管理者用ツール - メンテナンスと管理作業用のCLIコマンド

このスクリプトは以下の管理タスクを実行します：
- メモリクリーニング（重複行削除）
- ベクトルストア再構築
- バックエンド移行（SQLite ⇔ Qdrant）
- 重複検知
- メモリマージ
- 知識グラフ生成

使用例：
    # メモリクリーニング
    python admin_tools.py clean --persona nilou --key memory_20251101172801

    # ベクトルストア再構築
    python admin_tools.py rebuild --persona nilou

    # SQLite → Qdrant 移行
    python admin_tools.py migrate --source sqlite --target qdrant --persona nilou

    # 重複検知
    python admin_tools.py detect-duplicates --persona nilou --threshold 0.85

    # メモリマージ
    python admin_tools.py merge --persona nilou --keys memory_001 memory_002 memory_003

    # 知識グラフ生成
    python admin_tools.py generate-graph --persona nilou --format html
"""

import sys
import argparse
from typing import List, Optional
import sqlite3
from pathlib import Path

# プロジェクトモジュールをインポート
import config_utils
import persona_utils
import vector_utils
import analysis_utils


def clean_memory(persona: str, key: str) -> None:
    """メモリ内の重複行を削除"""
    print(f"🧹 Cleaning memory for persona: {persona}, key: {key}")
    
    # personaを設定
    persona_utils.current_persona.set(persona)
    db_path = persona_utils.get_db_path(persona)
    
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # メモリの内容を取得
        cursor.execute('SELECT content FROM memories WHERE key = ?', (key,))
        row = cursor.fetchone()
        
        if not row:
            print(f"❌ Memory not found: {key}")
            return
        
        content = row[0]
        lines = content.split('\n')
        original_count = len(lines)
        
        # 重複削除
        seen = set()
        unique_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
        
        cleaned_content = '\n'.join(unique_lines)
        removed_count = original_count - len(unique_lines)
        
        # 更新
        cursor.execute('UPDATE memories SET content = ? WHERE key = ?', (cleaned_content, key))
        conn.commit()
    
    print(f"✅ Cleaned {removed_count} duplicate lines from {key}")
    print(f"   Original: {original_count} lines → Cleaned: {len(unique_lines)} lines")


def rebuild_vector_store(persona: str) -> None:
    """ベクトルストアを再構築"""
    print(f"🔨 Rebuilding vector store for persona: {persona}")
    
    # personaを設定
    persona_utils.current_persona.set(persona)
    
    try:
        result = vector_utils.rebuild_vector_store()
        print(f"✅ {result}")
    except Exception as e:
        print(f"❌ Error rebuilding vector store: {e}")
        import traceback
        traceback.print_exc()


def migrate_backend(source: str, target: str, persona: str, upsert: bool = True) -> None:
    """バックエンド間でデータを移行"""
    print(f"🔄 Migrating {source} → {target} for persona: {persona}")
    
    # personaを設定
    persona_utils.current_persona.set(persona)
    
    try:
        if source == "sqlite" and target == "qdrant":
            result = vector_utils.migrate_sqlite_to_qdrant()
            print(f"✅ Migrated {result} memories to Qdrant")
        elif source == "qdrant" and target == "sqlite":
            result = vector_utils.migrate_qdrant_to_sqlite(upsert=upsert)
            print(f"✅ Migrated {result} memories to SQLite")
        else:
            print(f"❌ Invalid migration path: {source} → {target}")
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()


def detect_duplicates(persona: str, threshold: float = 0.85, max_pairs: int = 50) -> None:
    """重複または類似したメモリを検出"""
    print(f"🔍 Detecting duplicates for persona: {persona} (threshold: {threshold})")
    
    # personaを設定
    persona_utils.current_persona.set(persona)
    
    try:
        result = analysis_utils.detect_duplicate_memories(threshold=threshold, max_pairs=max_pairs)
        print(result)
    except Exception as e:
        print(f"❌ Error detecting duplicates: {e}")
        import traceback
        traceback.print_exc()


def merge_memories(persona: str, memory_keys: List[str], merged_content: Optional[str] = None,
                  keep_all_tags: bool = True, delete_originals: bool = True) -> None:
    """複数のメモリを1つにマージ"""
    print(f"🔗 Merging memories for persona: {persona}")
    print(f"   Keys: {', '.join(memory_keys)}")
    
    # personaを設定
    persona_utils.current_persona.set(persona)
    
    try:
        result = analysis_utils.merge_memories(
            memory_keys=memory_keys,
            merged_content=merged_content,
            keep_all_tags=keep_all_tags,
            delete_originals=delete_originals
        )
        print(f"✅ {result}")
    except Exception as e:
        print(f"❌ Merge error: {e}")
        import traceback
        traceback.print_exc()


def generate_knowledge_graph(persona: str, output_format: str = "html",
                             min_count: int = 2, min_cooccurrence: int = 1,
                             remove_isolated: bool = True) -> None:
    """知識グラフを生成"""
    print(f"📊 Generating knowledge graph for persona: {persona}")
    
    # personaを設定
    persona_utils.current_persona.set(persona)
    
    try:
        # グラフを構築
        graph = analysis_utils.build_knowledge_graph(
            min_count=min_count,
            min_cooccurrence=min_cooccurrence,
            remove_isolated=remove_isolated,
            persona=persona
        )
        
        # 出力形式に応じてエクスポート
        if output_format == "html":
            import os
            from datetime import datetime
            
            # 出力パスを生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = config_utils.get_data_dir()
            output_path = os.path.join(output_dir, f"knowledge_graph_{persona}_{timestamp}.html")
            
            result = analysis_utils.export_graph_html(
                graph, 
                output_path=output_path,
                title=f"Knowledge Graph - {persona}"
            )
            print(f"✅ Knowledge graph saved to: {result}")
        else:  # json
            result = analysis_utils.export_graph_json(graph)
            print(f"✅ Knowledge graph generated")
            print(result)
    except Exception as e:
        print(f"❌ Error generating knowledge graph: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="Memory MCP 管理者用ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='利用可能なコマンド')
    
    # clean コマンド
    clean_parser = subparsers.add_parser('clean', help='メモリの重複行を削除')
    clean_parser.add_argument('--persona', required=True, help='Persona名')
    clean_parser.add_argument('--key', required=True, help='メモリキー')
    
    # rebuild コマンド
    rebuild_parser = subparsers.add_parser('rebuild', help='ベクトルストアを再構築')
    rebuild_parser.add_argument('--persona', required=True, help='Persona名')
    
    # migrate コマンド
    migrate_parser = subparsers.add_parser('migrate', help='バックエンド間でデータを移行')
    migrate_parser.add_argument('--source', required=True, choices=['sqlite', 'qdrant'], help='移行元')
    migrate_parser.add_argument('--target', required=True, choices=['sqlite', 'qdrant'], help='移行先')
    migrate_parser.add_argument('--persona', required=True, help='Persona名')
    migrate_parser.add_argument('--no-upsert', action='store_true', help='上書きしない（SQLite→Qdrantのみ）')
    
    # detect-duplicates コマンド
    detect_parser = subparsers.add_parser('detect-duplicates', help='重複メモリを検出')
    detect_parser.add_argument('--persona', required=True, help='Persona名')
    detect_parser.add_argument('--threshold', type=float, default=0.85, help='類似度閾値 (0.0-1.0)')
    detect_parser.add_argument('--max-pairs', type=int, default=50, help='最大検出ペア数')
    
    # merge コマンド
    merge_parser = subparsers.add_parser('merge', help='複数のメモリをマージ')
    merge_parser.add_argument('--persona', required=True, help='Persona名')
    merge_parser.add_argument('--keys', nargs='+', required=True, help='マージするメモリキーのリスト')
    merge_parser.add_argument('--content', help='マージ後の内容（指定しない場合は自動結合）')
    merge_parser.add_argument('--no-keep-tags', action='store_true', help='タグを結合しない')
    merge_parser.add_argument('--no-delete', action='store_true', help='元のメモリを削除しない')
    
    # generate-graph コマンド
    graph_parser = subparsers.add_parser('generate-graph', help='知識グラフを生成')
    graph_parser.add_argument('--persona', required=True, help='Persona名')
    graph_parser.add_argument('--format', default='html', choices=['html', 'json'], help='出力形式')
    graph_parser.add_argument('--min-count', type=int, default=2, help='最小リンク出現回数')
    graph_parser.add_argument('--min-cooccurrence', type=int, default=1, help='最小共起回数')
    graph_parser.add_argument('--keep-isolated', action='store_true', help='孤立ノードを保持')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # コマンド実行
    if args.command == 'clean':
        clean_memory(args.persona, args.key)
    
    elif args.command == 'rebuild':
        rebuild_vector_store(args.persona)
    
    elif args.command == 'migrate':
        migrate_backend(args.source, args.target, args.persona, upsert=not args.no_upsert)
    
    elif args.command == 'detect-duplicates':
        detect_duplicates(args.persona, args.threshold, args.max_pairs)
    
    elif args.command == 'merge':
        merge_memories(
            args.persona,
            args.keys,
            merged_content=args.content,
            keep_all_tags=not args.no_keep_tags,
            delete_originals=not args.no_delete
        )
    
    elif args.command == 'generate-graph':
        generate_knowledge_graph(
            args.persona,
            args.format,
            args.min_count,
            args.min_cooccurrence,
            remove_isolated=not args.keep_isolated
        )


if __name__ == '__main__':
    main()

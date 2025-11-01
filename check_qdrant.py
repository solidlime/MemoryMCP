#!/usr/bin/env python3
"""
Qdrant Production Environment Verification Tool

本番環境のQdrantサーバーへの接続確認と状態チェックを行います。
"""
import sys
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
except ImportError:
    print("❌ Error: qdrant-client is not installed")
    print("Please run: pip install qdrant-client>=1.8.2")
    sys.exit(1)

import config_utils


def check_qdrant_connection(url: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Qdrantサーバーへの接続確認
    
    Args:
        url: Qdrant server URL (例: http://nas:6333)
        api_key: API key (optional)
    
    Returns:
        接続状態と情報を含む辞書
    """
    result = {
        "url": url,
        "connected": False,
        "error": None,
        "collections": [],
        "total_vectors": 0,
        "server_info": None,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # クライアント作成
        client = QdrantClient(url=url, api_key=api_key)
        
        # 接続確認（コレクション一覧取得）
        collections = client.get_collections()
        result["connected"] = True
        
        # コレクション情報の取得
        collection_details = []
        total_vectors = 0
        
        for collection in collections.collections:
            try:
                # コレクションの詳細情報を取得
                collection_info = client.get_collection(collection.name)
                
                vector_count = collection_info.points_count or 0
                total_vectors += vector_count
                
                collection_details.append({
                    "name": collection.name,
                    "vectors_count": vector_count,
                    "config": {
                        "vector_size": collection_info.config.params.vectors.size if hasattr(collection_info.config.params.vectors, 'size') else "unknown",
                        "distance": collection_info.config.params.vectors.distance.name if hasattr(collection_info.config.params.vectors, 'distance') else "unknown"
                    }
                })
            except Exception as e:
                collection_details.append({
                    "name": collection.name,
                    "error": str(e)
                })
        
        result["collections"] = collection_details
        result["total_vectors"] = total_vectors
        
        # サーバー情報の取得を試みる
        try:
            # Qdrant のバージョン情報等を取得
            # Note: qdrant-clientのバージョンによってはこのAPIがないかも
            result["server_info"] = "Connected successfully"
        except:
            pass
            
    except Exception as e:
        result["error"] = str(e)
        result["connected"] = False
    
    return result


def print_report(result: Dict[str, Any]) -> None:
    """
    接続確認結果をわかりやすく表示
    """
    print("=" * 70)
    print("🔍 Qdrant Production Environment Verification Report")
    print("=" * 70)
    print(f"📅 Timestamp: {result['timestamp']}")
    print(f"🌐 Target URL: {result['url']}")
    print()
    
    if result["connected"]:
        print("✅ Connection Status: CONNECTED")
        print()
        
        if result["collections"]:
            print(f"📊 Collections Found: {len(result['collections'])}")
            print(f"📈 Total Vectors: {result['total_vectors']}")
            print()
            
            print("-" * 70)
            print("📦 Collection Details:")
            print("-" * 70)
            
            for coll in result["collections"]:
                if "error" in coll:
                    print(f"\n❌ {coll['name']}: Error - {coll['error']}")
                else:
                    print(f"\n✨ {coll['name']}")
                    print(f"   Vectors: {coll['vectors_count']}")
                    if "config" in coll:
                        print(f"   Vector Size: {coll['config']['vector_size']}")
                        print(f"   Distance Metric: {coll['config']['distance']}")
        else:
            print("ℹ️  No collections found (empty Qdrant instance)")
            
    else:
        print("❌ Connection Status: FAILED")
        print(f"💔 Error: {result['error']}")
        print()
        print("🔧 Troubleshooting Tips:")
        print("   1. Check if Qdrant server is running")
        print("   2. Verify the URL is correct (e.g., http://nas:6333)")
        print("   3. Check network connectivity")
        print("   4. Verify firewall settings")
    
    print()
    print("=" * 70)


def main():
    """
    メイン処理: 設定ファイルまたは引数からQdrant URLを取得して接続確認
    """
    # 設定を読み込み
    config = config_utils.load_config()
    
    # コマンドライン引数から URL を取得（指定されていれば）
    qdrant_url = config.get("qdrant_url", "http://localhost:6333")
    qdrant_api_key = config.get("qdrant_api_key")
    
    if len(sys.argv) > 1:
        qdrant_url = sys.argv[1]
    
    if len(sys.argv) > 2:
        qdrant_api_key = sys.argv[2]
    
    print()
    print("🚀 Starting Qdrant Connection Check...")
    print(f"📍 Target: {qdrant_url}")
    print()
    
    # 接続確認実行
    result = check_qdrant_connection(qdrant_url, qdrant_api_key)
    
    # 結果を表示
    print_report(result)
    
    # 終了コード
    sys.exit(0 if result["connected"] else 1)


if __name__ == "__main__":
    main()

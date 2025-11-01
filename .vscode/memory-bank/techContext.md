# Tech Context: Memory MCP

## 技術スタック
- **Python 3.12+**（venv-rag）
- **FastMCP**（MCPサーバー/依存関数 get_http_request）
- **LangChain**（RAGフレームワーク）
- **FAISS**（ベクトル検索）
- **sentence-transformers**（CrossEncoderリランカー）
- **Docker / Docker Compose**（コンテナ化）
- **Obsidian**（知識グラフ可視化/オプション）
- **Jinja2, Tailwind, Chart.js, PyVis**（Webダッシュボード/可視化）

---

## 依存関係
- FastMCP 0.9.0+
- LangChain 1.0+
- faiss-cpu
- sentence-transformers 2.2.0+
- SQLite3（標準）

---

## データ形式
- **SQLite**: memories/operationsテーブル（tagsはJSON配列）
- **Persona Context**: persona_context.json（ユーザー/ペルソナ/感情/状態/環境/関係性/時刻）
- **Operations Log**: memory_operations.log（JSONL）

---

## ディレクトリ構造
```
memory-mcp/
├── memory_mcp.py
├── db_utils.py
├── persona_utils.py
├── vector_utils.py
├── tools_memory.py
├── config.json
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── test_tools.py
├── memory/
│   ├── default/ ...
│   └── {persona}/ ...
├── .cache/ ...
├── .vscode/memory-bank/ ...
└── memory_operations.log
```

---

## 実装詳細
- PersonaはX-Personaヘッダーで完全分離（DB/ベクトル/コンテキスト）
- get_current_persona()で動的にパス解決
- RAG: Embeddings（cl-nagoya/ruri-v3-30m）→ FAISS → CrossEncoder（hotchpotch/japanese-reranker-xsmall-v2）
- CRUD時にDirtyフラグ→アイドル時にベクトル再構築
- Webダッシュボード: Jinja2+Tailwind+Chart.js+PyVisで可視化/API連携

---

## 設定管理
- config.jsonでモデル・デバイス・サーバー・再構築モード等を管理
- ホットリロード対応

---

## パフォーマンス・スケーラビリティ
- Embeddings/Rerankerは単一ロード
- FAISSは数万件まで高速
- Rerankingはtop_k*3のみ
- メモリ消費: ~180MB（モデル+FAISS）
- 検索速度: RAGで60-110ms（40件時）

---

## セキュリティ
- Persona単位で完全分離
- persona名はファイルシステムセーフにバリデーション
- pickleデシリアライズは信頼環境のみ
- データはローカル保存、暗号化なし（個人用途）

---

## 開発環境
- VS Code（Pylance, Python, Copilot推奨）
- venv-rag仮想環境
- Docker 20.10+（推奨）

---

## トラブルシューティング
- Rerankerエラー: sentence-transformersのインストール確認
- DBマイグレーション: サーバー再起動で自動実行
- モデルDLエラー: 手動DLで解決

---

## 参考: 主要コード例
- get_current_persona(), get_db_path(), search_memory_rag(), load_memory_from_db() など
- 詳細は各モジュール・README参照

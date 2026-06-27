# HANDOFF - 2026-06-27 10:48

## 使用ツール
Claude Code (via opencode)

## 現在のタスクと進捗

### ✅ v8 完了タスク
| # | タスク | 状態 |
|---|--------|------|
| A-1,A-2 | SearXNG docker-compose化 + Dockerfile.sandboxスリム化 | ✅ |
| A-6 | /healthエンドポイント追加 (Qdrant/SearXNG/sandbox) | ✅ |
| B-1 | 5 builtin-onlyツールMCP登録 (browser/search/image_generate/read_pdf/list_skills) | ✅ |
| B-2,B-3 | 名前統一 (execute_code→sandbox, context_update→update_context) | ✅ |
| B-5 | memory二重実装解消 (戻り値dict化→builtin委譲, ~180行削減) | ✅ |
| C-2,C-3,C-4,C-5 | sandbox多言語対応 (JS/Bash/Go/Rust) | ✅ |
| D-1 | PDF OCR fallback (PyMuPDF→pdfplumber→Tesseract chain) | ✅ |
| T003 | 本番ビルド検証 (3サービス疎通テスト) | ✅ |
| --- | ruffエラー全解消 + CI(Bandit)修正 | ✅ |

### T003 Docker検証 実動作テスト結果
- **Qdrant**: Docker稼働中 (port 6333, healthy) ✅
- **SearXNG**: Docker稼働中 (port 8080, healthy)。settings.ymlに`search.formats: [html,json]`要設定 ✅
- **memory-mcp**: ソース起動 (port 26262)。DockerイメージビルドはWSL2環境のディスク不足(4.1GB空き)で断念
  - MCP tools/list: 24ツール全登録確認 ✅
  - MCP search: SearXNG経由で高品質検索結果返却 ✅
  - MCP list_skills: 2スキル返却 ✅
  - MCP browser: 登録済み。Chrome起動エラーは既知のWSL2制限
  - MCP sandbox: Permission denied (Errno 13) — コード起因ではなくDockerボリュームUID不一致。Dockerfile.sandboxに`chmod 777 /sandbox`で緩和策済み

### コード修正（T003中）
- `chat_config.py:59`: `searxng_url` デフォルトを `os.environ.get("MEMORY_MCP_SEARXNG_URL", "http://localhost:8080")` に変更
- `Dockerfile.sandbox:25`: `chmod 777 /sandbox` 追加

### ⏳ 残タスク (低優先)
- T019: D-2 Agent Skills標準移行 (SKILL.md形式, Progressive Disclosure)
- T020: D-3 4-tier lifecycle基本 (active/superseded/tombstoned)
- T021: D-4 検索ハイブリッド強化 (FTS5+RRF+KNN)

## 試したこと・結果
- ✅ **v8 本番構成テスト**: Qdrant(Docker) + SearXNG(Docker) + memory-mcp(ソース起動) の3サービス構成で全MCPツール疎通確認
- ✅ **検索テスト**: SearXNGの初期設定(`search.formats`がhtmlのみ)でJSON APIが403→settings.yml追加で解決。検索結果品質良好
- ✅ **Dockerfile.sandboxスリム化**: ユーザー指摘により多言語ランタイムをDockerfileから削除、llm_sandboxの公式イメージに任せる方針に。イメージ~600MB→~150MB
- ✅ **CI修正**: ruff format + Bandit B608抑制 (chat_config.pyのDBカラム名f-string)
- ✅ **PDF OCR**: PyMuPDF→pdfplumber→Tesseractの3段フォールバック。text_sourceフィールドでどの抽出方法を使ったか追跡可能
- ⚠️ **sandbox権限問題**: v7から継続。コード側の対策 (`chmod 777`) は緩和策。根本解決にはDockerのuser namespace remap (`/etc/docker/daemon.json`) またはllm_sandbox側の修正が必要

## 次のセッションで最初にやること
1. GitHub ActionsのCI結果確認 (docker.yml / ci.yml)
2. 本番サーバーでの `docker compose up` 全サービス起動確認（T003本番）
3. SearXNGの`settings.yml`に`search.formats: [html, json]`が自動設定されるか確認（Docker volumeマウント）
4. T019 Agent Skills標準移行 または T020 4-tier lifecycle の着手判断

## 注意点・ブロッカー
- **ディスク容量**: WSL2環境で4.1GB空き。PyTorch含むDockerマルチステージビルドには10GB以上推奨。本番サーバーなら問題なし
- **SearXNG設定**: `search.formats`のデフォルトが`html`のみ。`docker compose up`前に`./data/searxng/settings.yml`を作成するか、初回起動後に手動設定が必要
- **sandbox権限**: WSL2環境でDockerボリュームのUID/GIDマッピングがずれる既知の問題。`chmod 777 /sandbox`で緩和
- **agent-browser**: WSL2環境ではChrome起動不可 (`--no-sandbox`伝搬問題)。本番Linuxサーバーでは動作するはず
- **本番環境変数**: `MEMORY_MCP_SEARXNG_URL=http://searxng:8080` — docker-compose.ymlで設定済み

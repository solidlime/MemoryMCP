# TODO: マルチモーダルLLM対応

## フェーズ1: 画像生成基盤 (DALL-E + SD)
- [ ] 1.1 `infrastructure/image_gen/` パッケージ作成
  - [ ] 1.1.1 `base.py` — ImageGenProvider 抽象クラス (`generate(prompt, size, quality, n) -> list[GeneratedImage]`)
  - [ ] 1.1.2 `dalle.py` — DALL-E 3 実装 (openai.images.generate)
  - [ ] 1.1.3 `stability.py` — SD WebUI API 実装 (POST /sdapi/v1/txt2img)
  - [ ] 1.1.4 `factory.py` — get_image_gen_provider(config) ファクトリ
- [ ] 1.2 `domain/chat_config.py` — image_gen 系フィールド追加
- [ ] 1.3 DBマイグレーション — v026 で image_gen カラム追加
- [ ] 1.4 `events.py` — ImageGenStartSSE, ImageGenResultSSE 追加
- [ ] 1.5 `tools/definitions.py` — image_generate ツール定義 + _BUILTIN_DISPATCH 登録
- [ ] 1.6 `tools/builtin.py` — _handle_image_generate() 実装
- [ ] 1.7 `sections/chat.py` — 画像生成設定UI (有効/無効, プロバイダ, モデル, SD URL)
- [ ] 1.8 `static/chat.js` — image_gen_start / image_gen_result イベント処理, 画像表示
- [ ] 1.9 `static/chat.css` — 生成画像のスタイル (ローディングスピナー, 画像カード)

## フェーズ2: PDF解析
- [ ] 2.1 `tools/definitions.py` — read_pdf ツール定義 + _BUILTIN_DISPATCH 登録
- [ ] 2.2 `tools/builtin.py` — _handle_read_pdf() 実装 (fitz + pdfplumber)
- [ ] 2.3 `domain/chat_config.py` — pdf_max_size_mb フィールド追加
- [ ] 2.4 DBマイグレーション — v027 で pdf_max_size_mb カラム追加

## フェーズ3: テスト・検証
- [ ] 3.1 Python 単体テスト
  - [ ] 3.1.1 `test_image_gen_providers.py` — DALL-E / SD モックテスト
  - [ ] 3.1.2 `test_read_pdf.py` — PDF解析テスト (テキスト/テーブル/画像抽出)
  - [ ] 3.1.3 `test_chat_service.py` — image_gen_* イベントテスト, ツール呼び出しテスト
- [ ] 3.2 統合テスト
  - [ ] 3.2.1 PDF添付→ツール呼び出し→応答のE2Eフロー
  - [ ] 3.2.2 画像生成→チャットログ表示のE2Eフロー
- [ ] 3.3 ブラウザテスト (agent-browser)
  - [ ] 3.3.1 画像生成設定UI切り替えテスト
  - [ ] 3.3.2 生成画像のチャットログ表示確認
  - [ ] 3.3.3 PDF添付→解析→応答表示の全フロー
- [ ] 3.4 CI統合 — ruff / pytest / bandit 全パス確認

## テスト戦略 (アイスクリームコーン型)

```
         ▲ 手動探索テスト (spot check)
        /|\
       / | \       E2Eテスト (agent-browser)
      /  |  \      
     /   |   \     統合テスト (pytest + 実API/実ファイル)
    /    |    \
   /     |     \   単体テスト (pytest + mock)
  ─────────────────────────────────────
  多層テストで網羅性を担保。下層ほど多く、上層ほどクリティカルパス。
```

### テスト環境セットアップ

#### 現在の開発環境 (Linux Native)
| ツール | 状態 | バージョン |
|--------|------|-----------|
| Python | ✅ | 3.14.4 |
| Node/npm | ✅ | v22.22.1 |
| Docker | 要インストール | `curl -fsSL https://get.docker.com \| sh` |

#### 環境準備コマンド
```bash
# 0. Docker (Qdrant + Sandbox用)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 再ログイン or newgrp docker

# 1. Python依存 (テスト・lint・PDF解析)
pip3 install pytest pytest-asyncio pytest-mock ruff PyMuPDF pdfplumber

# 2. agent-browser (ブラウザテスト用)
npm install -g @agent-browser/cli

# 3. Qdrant起動
docker compose up -d qdrant
```

#### テスト実行手順
```bash
# 単体テスト (Qdrant不要、mockで完結)
cd /home/rausraus/code/MemoryMCP
python3 -m pytest tests/unit/ -x -q

# 統合テスト (Qdrant Dockerが必要 → 事前に docker compose up -d qdrant)
python3 -m memory_mcp.main &
python3 -m pytest tests/integration/ -x -q
pkill -f memory_mcp

# ブラウザテスト (Qdrant + サーバー + agent-browser が必要)
python3 -m memory_mcp.main &
agent-browser open http://localhost:8765
# ← テストシナリオ実行
pkill -f memory_mcp
```

#### agent-browser テストシナリオ例
1. ペルソナ選択 → チャットタブ表示確認
2. 画像生成設定セクションが表示されること
3. PDF添付 → メッセージ送信 → ツール呼び出し → 応答に解析結果が含まれること
4. 画像生成ツール呼び出し → チャットログに画像が表示されること

### テストデータ
- `tests/fixtures/sample.pdf` — テキスト+テーブル+画像を含むテストPDF (2ページ, ~100KB)
- `tests/fixtures/sample_tables.pdf` — 複数テーブル含むPDF
- DALL-Eモック: `tests/fixtures/dalle_response.json`
- SDモック: `tests/fixtures/sd_response.json`

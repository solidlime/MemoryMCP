# KNOWLEDGE - ドメイン知識・調査結果

## 業務・ドメイン知識
- Hindsight (vectorize-io/hindsight) はエージェント向け長期記憶システム。Retain/Recall/Reflect の3操作モデル
- MemoryMCP は Hindsight の主要機能の半分以上を既に実装済み（hybrid search, RRF, cross-encoder, reflection, entity extraction）
- ギャップとして date_range 検索フィルタ、重要度自動評価、関係性自動抽出、メンタルモデル抽象化を特定

## 調査・リサーチ結果
- Hindsight 公式: https://hindsight.vectorize.io
- Hindsight GitHub: https://github.com/vectorize-io/hindsight (13.2k stars)
- MemoryMCP の検索パイプライン: MCP tool → SearchQuery → SearchEngine → Strategies → SQLite/Qdrant
- LLM 基盤: infrastructure/llm/ 配下に Anthropic/OpenAI/OpenRouter の3プロバイダ対応

## 技術的な知見

### P1: date_range 検索統合
- `parse_date_range()` は日本語相対日時表現（昨日、先週、7d等）を解析済み
- 検索パイプラインの各層（Protocol → Strategy → Repository → Engine）に date_from/date_to を追加
- Qdrant は payload に created_at がないため、アダプタ層でポストフィルタ（fetch_limit×3 → 日付フィルタ → top_k）
- SQLite は `created_at` カラムに既存インデックス（v007 migration）あり

### P2+P3: 記憶エンリッチメント
- 1回のLLM呼出で importance + entity relations を同時抽出（コスト最適化）
- MemoryService.create_memory() 内で best-effort で実行（例外時も作成は継続）
- importance 明示指定時（≠0.5）は完全スキップ
- type_classifier + entity_extractor の結果をLLMプロンプトに注入しトークン削減
- JSON structured output で確実なパース

### P4: メンタルモデル抽象化
- type_classifier のタイプタグ（decision/preference/milestone/problem/emotional）を利用して記憶をグループ化
- 同一タイプの記憶が N 件（デフォルト3）蓄積されたら LLM でパターン抽象化
- タイプ別に最終抽象化時刻をメタ記憶で管理し、重複実行を防止
- Reflection（24h全記憶）とは異なり、タイプ特化・蓄積トリガーの設計

## 決定事項と理由
- **P2+P3 統合**: 別々のLLM呼出より1回に統合する方がコスト効率が良い。importanceとrelationは同じ記憶から抽出するため情報の重複が多い
- **P2 即時処理**: バッチ処理より即時処理の方がシンプル。importance は作成時に決まるべき情報
- **P4 バッチ処理**: メンタルモデルは複数記憶の蓄積を待つ必要があるため、バッチ（トリガー）方式が自然
- **Qdrant ポストフィルタ方式**: payload に created_at を追加するには全upsert箇所の修正と再構築が必要。アダプタ層フィルタの方が低侵襲

## フロントエンド改善（2026-05-15）で得た知見

### chat.py 構造
- 2190行→1910行に削減（死にコード280行削除）
- CSSは12-416行、JSは約700行以降に分離（Python文字列リテラル内）
- 設定パネルHTMLは `<details>` アコーディオン化（10セクション→9セクション）
- Sandbox panel JSは完全に削除。`sandboxLog`/`sandboxRunBlock`/`sandboxAddArtifact`/`renderCodeBlock` はコードブロックRunボタン用に保持
- `MEMORY_TOOL_NAMES` はMCPツール5個→builtin含む17個に拡張

### バックエンド連携
- `extract_max_tokens` と `enable_memory_tools` は既に `ChatConfig` に存在（UI追加のみで可）
- `debug_mode` は `ChatConfig` に新規追加
- `/api/chat/{persona}/tool` エンドポイントを新規追加（builtin tool直接実行用）
- `promise_cancel` を `builtin.py` + `definitions.py` に追加（`goal_cancel` 同パターン）
- `memory_search` builtin上限を10→200に

### テスト修正
- sandboxターミナル履歴（ArrowUp/ArrowDown）テストをCoding Agent移行に合わせて更新
- sandboxInstallPackages/sandboxResetテストをsandboxRunBlockに変更
- `search_memory` の `mode` パラメータ削除に伴いテストの `mode="keyword"` を `mode="hybrid"` に

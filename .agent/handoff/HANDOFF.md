# HANDOFF

## 最終作業: Hindsight 分析・PLAN.md 作成 (2026-05-13 23:30)

### 背景
vectorize-io/hindsight（13.2k stars, エージェント向け長期記憶システム）を分析し、MemoryMCP とのギャップ・改善候補を特定。PLAN.md に方針を記述。

### 分析サマリー
MemoryMCP は Hindsight の主要機能の**半分以上を既に実装済み**。検索アーキテクチャ（hybrid + RRF + cross-encoder + graph）、Reflect、矛盾検出、エンティティ抽出・タイプ分類等が稼働中。

### 特定されたギャップ（優先度順）

| 優先度 | 項目 | 概要 |
|--------|------|------|
| 🔴 P1 | date_range 検索統合 | parse_date_range() 実装済み。search_keyword() / Qdrant search() に未統合。繋ぐだけ |
| 🟠 P2 | 重要度自動評価 | importance が手動のみ。type_classifier 活用 or LLM 評価 |
| 🟡 P3 | 関係性自動抽出 | エンティティ間の関係性を自動抽出（LLM or 日本語構文解析） |
| 🟢 P4 | メンタルモデル抽象化 | 複数記憶からのパターン抽出・抽象化レイヤー。新規設計 |

### 次セッションでの作業
1. `.spec/PLAN.md` を読み、SPEC.md・TODO.md を作成（SDD フローに従う）
2. 優先度に従い実装着手（P1→P2→P3→P4）
3. 実装前には必ず `.spec/` の4ファイルを確認・更新

### 参考情報
- Hindsight 公式: https://hindsight.vectorize.io
- Hindsight GitHub: https://github.com/vectorize-io/hindsight
- 主要な3操作モデル: Retain / Recall / Reflect
- MemoryMCP の検索フロー: `engine.py` → `RRFRanker` → `RerankerModel`
- LLM 連携: `infrastructure/llm/`（Anthropic/OpenAI/OpenRouter）
- 埋め込み: `infrastructure/embedding/model.py`（ruri-v3, sentence-transformers）

### 現状
- Spec ファイルはテンプレート状態（SPEC.md, TODO.md は初期状態）
- PLAN.md に改善候補を記述済み
- CI 最終状態: ✅ 全グリーン（Unit 371 + Integration 80 + E2E 75）

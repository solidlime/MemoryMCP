# PLAN - やりたいこと

## Hindsight 分析（2026-05-13）
vectorize-io/hindsight（13.2k stars）を分析し、MemoryMCP とのギャップを特定。

### 既に実装済み（Hindsight相当以上）
- Semantic 検索: Qdrant + ruri-v3 ローカル埋め込み
- Keyword 検索: SQLite LIKE
- Graph 検索: entity_graph / entity_search / entity_add_relation
- RRF 融合: RRFRanker（k=60）
- Cross-encoder リランキング: RerankerModel（japanese-reranker-xsmall-v2）
- Reflect（内省）: reflection.py（Generative Agents スタイル）
- 矛盾検出: check_contradictions
- セッション要約: LLMベース + 日次要約ワーカー
- エンティティ抽出: 正規表現ベース（人物・場所）
- 自動タイプ分類: 5タイプ（decision/preference/milestone/problem/emotional）
- LLM連携: Anthropic / OpenAI / OpenRouter

### 改善候補（優先度順）

#### 🔴 P1: date_range 検索フィルタ統合
- parse_date_range() は実装済みだが、実際の検索SQLに未統合
- search_keyword() と Qdrant search() に date_range フィルタを追加
- これだけで時系列検索が機能するようになる

#### 🟠 P2: 重要度の自動評価
- 現在 importance は手動設定のみ（デフォルト0.5）
- 案1: LLM で自動評価（openai/anthropic API使用）
- 案2: ヒューリスティック（単語数・感情強度・タイプなどから計算）
- type_classifier の結果を importance 計算に活用できるかも

#### 🟡 P3: 関係性の自動抽出
- エンティティ抽出はあるが、エンティティ間の関係性は手動 add_relation のみ
- 案1: LLM で「AはBの〜」パターンを抽出
- 案2: 日本語構文解析（係り受け）で抽出
- Hindsight の Retain 相当の完全自動構造化を目指す

#### 🟢 P4: メンタルモデル / 抽象化レイヤー
- 複数記憶からのパターン抽出・抽象化
- 例: 「ユーザーは朝コーヒーを飲む」×3回 → 「ユーザーは朝コーヒーを飲む習慣がある」
- 新規設計が必要。Hindsight の Mental Models を参考に
- Reflection の延長線上にある概念

#### その他（余裕があれば）
- BM25 キーワード検索（現在 LIKE）
- 感情自動分析（emotion_type 自動設定）
- Ollama 等ローカルLLM対応
- LongMemEval ベンチマーク参加検討

### MemoryMCP の独自強み（維持すべき）
- MCP ネイティブ（REST + MCP 両対応）
- ペルソナ管理（感情・装備・状態）
- SQLite 軽量運用
- LLM なしで動作可能
- Memory Blocks / 物理アイテム管理

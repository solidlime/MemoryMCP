# SPEC - 技術仕様・要件定義

## P1: date_range 検索フィルタ統合 🔴

### 現状
- `parse_date_range()` (`time_utils.py:100`) 実装済み。日本語相対日時表現（昨日、先週、7d等）を `(start, end)` datetime に変換
- `date_range` パラメータは MCP ツール（`tools.py:521`）→ `SearchQuery`（`engine.py:34`）まで到達している
- **だが検索実行時に使われていない**。smart/memorag モードでサブクエリに伝播されるだけ

### 要件
- `search_keyword()` (SQLite) と `search()` (Qdrant) の両方で `date_range` によるフィルタリングを有効化
- `SearchEngine` で `parse_date_range()` を実行し、`created_at` が範囲内の記憶のみ返す

### 技術設計
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| Repository Protocol | `domain/memory/repository.py:29` | `search_keyword(query, limit)` → `search_keyword(query, limit, date_from, date_to)` |
| KeywordSearchStrategy | `domain/search/strategies.py:12` | `search(query, limit)` → `search(query, limit, date_from, date_to)` |
| SemanticSearchStrategy | `domain/search/strategies.py:19` | 同上 |
| SQLite実装 | `infrastructure/sqlite/memory_repo.py:197` | SQL WHERE 句に `created_at BETWEEN ? AND ?` 追加 |
| Qdrant実装 | `infrastructure/qdrant/adapter.py:97` | Qdrant payload filter（`must` conditions）で `created_at` 範囲指定 |
| Adapter層 | `application/use_cases.py:26-58` | date_range パラメータのパススルー |
| SearchEngine | `domain/search/engine.py:68` | `parse_date_range(query.date_range)` を実行し、各戦略に `(date_from, date_to)` を渡す |
| 検索モード | `engine.py:114-158` | keyword/semantic/hybrid 全モードで date_filter 適用 |

### 非機能要件
- パフォーマンス: SQLite `created_at` カラムにインデックスがあるか確認。なければ追加
- 後方互換: `date_range=None` → 全期間（既存動作を維持）

---

## P2+P3 統合: 記憶エンリッチメント（重要度 + 関係性自動抽出）🟠🟡

### 現状
- `Memory.importance` はデフォルト 0.5、手動設定のみ
- `type_classifier` はタイプ分類を自動実行済み（無料・即時）
- `SimpleEntityExtractor` が正規表現でエンティティを抽出。関係性は `entity_add_relation` で手動設定のみ
- `MemoryService.create_memory()` → エンティティ抽出 → DB保存。この間に enrichment を挟む

### 要件
- **1回の LLM 呼び出し**で importance スコア + エンティティ間関係性を同時に抽出
- 記憶作成時に同期的に実行（`create_memory()` の一部として）
- `importance` が明示指定された場合はスキップ（既存動作優先）
- 設定でオン/オフ切替可能（LLM未設定環境ではスキップ）

### 技術設計

#### 新規: MemoryEnricher（統合LLM呼び出し）
| 項目 | 内容 |
|------|------|
| ファイル | `infrastructure/llm/memory_enricher.py` |
| 入力 | 記憶 content, type_classifier のタイプ分類結果, 抽出済みエンティティ一覧 |
| 出力 | `{importance: float, relations: [{source, target, type, confidence}]}` |
| プロンプト | 日本語で「この記憶の長期保持価値（0.0-1.0）と、含まれるエンティティ間の関係性を抽出せよ」 |
| JSON出力 | Structured output（JSON mode）で確実にパース |

#### 変更箇所
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| 新規: MemoryEnricher | `infrastructure/llm/memory_enricher.py` | LLM 呼び出し + JSON パース + importance clamp |
| 新規: EnrichmentResult | `domain/memory/enrichment.py` | `EnrichmentResult` データクラス（importance + relations） |
| MemoryService | `domain/memory/service.py:31` | `create_memory()` で type_classifier → entity_extract → MemoryEnricher（LLM）の順に実行 |
| 設定 | `config/settings.py` | `memory_enrichment_enabled: bool = True` |
| LLM Provider | `infrastructure/llm/` | 既存の Anthropic/OpenAI/OpenRouter をそのまま使用 |

#### 処理フロー
```
create_memory(content, importance=None, ...)
  ↓
type_classifier.auto_tags(content)          # 無料・即時
  ↓
entity_extractor.extract(content)           # 無料・即時
  ↓
if importance is None AND enrichment_enabled:
    MemoryEnricher.enrich(content, type_tags, entities)  # 1回のLLM呼出
    → importance = result.importance       # P2: 重要度
    → entity_service.add_relation(...) × N  # P3: 関係性自動登録
  ↓
MemoryRepository.save(memory)
```

#### LLMコスト削減策
1. **importance 明示指定時は LLM スキップ**: ユーザーが明示的に importance を指定したら enrichment 全体をスキップ
2. **type_classifier を先に実行**: LLM プロンプトにタイプ分類結果を含めることで、LLM の判断を補助・トークン削減
3. **entity_extractor を先に実行**: 抽出済みエンティティ一覧をプロンプトに含め、LLM がエンティティを再抽出する必要をなくす
4. **短い記憶はスキップ可能**: 設定 `enrichment_min_chars`（デフォルト 10）以下の記憶は LLM スキップ

### 関係タイプ候補
- `knows` / `works_with` / `manages` / `created` / `located_in` / `part_of` / `related_to`

---

## P4: メンタルモデル / 抽象化レイヤー 🟢

### 現状
- Reflection（`reflection.py`）: 24時間以内の記憶から LLM で洞察を生成。`importance_sum >= threshold` で発火
- Session Summarization（`summarizer.py`）: 会話セッションの要約
- **複数記憶からのパターン抽象化は未実装**

### 要件
- 複数の関連記憶から繰り返しパターンを抽出し、抽象化された「メンタルモデル」を生成
- 例: "ユーザーは朝コーヒーを飲む" ×3 → "ユーザーは朝コーヒーを飲む習慣がある"
- Reflection の延長線上に位置付け、既存のリフレクションエンジンを拡張

### 技術設計
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| 拡張: ReflectionEngine | `application/chat/reflection.py` | パターン抽象化用の新しいプロンプトと処理ロジック追加 |
| 新規: MentalModel | `domain/memory/mental_model.py` | `MentalModel` エンティティ（内容・元記憶キー一覧・confidence） |
| 新規: PatternDetector | `application/chat/pattern_detector.py` | 同一タグ・同一タイプの記憶群をクラスタリングし、LLM で抽象化 |
| トリガー | - | 同一タイプの記憶が N 件（デフォルト3）蓄積されたら発火 |
| 記憶として保存 | - | `tags=["mental_model", "abstracted"]`, `importance=0.85` |
| 設定 | `config/settings.py` | `mental_model_enabled: bool = True`, `mental_model_min_samples: int = 3` |

### 既存 Reflection との違い
| 項目 | Reflection（既存） | Mental Model（新規） |
|------|---------------------|---------------------|
| 対象 | 24時間以内の全記憶 | 同タイプ・同タグの複数記憶 |
| 出力 | 洞察・気づき | 抽象化されたパターン・習慣 |
| トリガー | importance 合計値 | 記憶の蓄積数 |
| タグ | `["reflection"]` | `["mental_model", "abstracted"]` |

### LLMコスト
- バッチ処理（N件蓄積 → 1回LLM）なので、P2+P3 より呼出頻度は低い
- トリガー時に同一タイプ記憶群を1つのプロンプトにまとめて抽象化

---

## 非機能要件（全体共通）
- パフォーマンス: P1 は軽量（WHERE句追加のみ）。P2+P3 はLLM 1回/記憶（設定でオフ可）。P4 はバッチ発火
- 後方互換: 全機能は設定でオン/オフ切替可能。デフォルト: P1=ON, P2+P3=ON, P4=ON
- テスト: 各機能にユニットテスト必須。P1 は SQLite 日付フィルタテスト、P2+P3/P4 は LLM モックテスト
- セキュリティ: LLM 呼び出し時は既存 `infrastructure/llm/` 基盤に従う

## 技術構成
- 言語: Python 3.11+
- 既存インフラ: SQLite, Qdrant, LLM基盤（infrastructure/llm/）
- 新規依存: なし

## データ構造
- `SearchQuery.date_range: str | None` → `parse_date_range()` → `(datetime | None, datetime | None)`
- `EnrichmentResult`: `{importance: float, relations: [{source, target, type, confidence}]}`
- `MentalModel`: `{content, source_memory_keys: list[str], confidence: float, abstracted_at: datetime}`

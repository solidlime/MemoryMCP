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

---

# フロントエンド・ツール改善（2026-05-15）

## 🔴 Phase 1: バグ修正

### F001: 旧サンドボックスパネル死にコード削除
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/api/http/sections/chat.py` |
| CSS削除範囲 | 255-416行（`#sandbox-panel` 全スタイル） |
| JS削除範囲 | 1665-2100行（Sandbox Panel JS全体） |
| 補足 | `#sandbox-panel`, `#sandbox-terminal` 等のDOM要素は既に存在しない。Coding Agentパネル（coding_agent.py）が現行のサンドボックスUI |

### F002: MEMORY_TOOL_NAMES にbuiltinツール追加
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/api/http/sections/chat.py:1673` |
| 現状 | `Set(['memory', 'search_memory', 'update_context', 'item', 'get_context'])` — MCPツール5個のみ |
| 追加対象 | `memory_create`, `memory_search`, `memory_update`, `context_update`, `context_recall`, `goal_create`, `goal_achieve`, `goal_cancel`, `promise_create`, `promise_fulfill`, `promise_cancel`, `invoke_skill` |
| 追加後 | Set に上記12個を追加 → メモリパネルにbuiltinツール結果表示 |

### F003: ~~caAppendOutput グローバル公開~~ → **実装済み**
| 項目 | 内容 |
|------|------|
| 状況 | `coding_agent.py:598` に `window.caAppendOutput = _appendOutput` 既存。chat.py:1763-1764 から呼出済み |
| 対応 | スキップ（完了） |

### F004: switchSandboxTab/sandboxExecuteCmd 二重定義削除
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/api/http/sections/chat.py` |
| 第1定義 | 1744-1754行（2タブ用: terminal, files）、1819-1841行（bash固定） |
| 第2定義 | 2057-2069行（3タブ用: terminal, files, artifacts）、2071-2100行（言語セレクタ使用） |
| 対応 | 第1定義を削除。第2定義はF001で削除される範囲内のためF001とまとめて対応 |

### F005: promise_cancel ツール追加
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/application/chat/tools/builtin.py` + `definitions.py` |
| 設計 | `goal_cancel` と同パターン: `promise_create`/`promise_fulfill` に対し `promise_cancel` を追加 |
| 実装 | `memory_service.get_by_tags(["promise", "active"])` → マッチ → `update_memory(key, tags=["promise", "cancelled"])` |

### F006: sandbox_files list 空問題 → 実装済み（要確認）
### F007: bash `!` プレフィックス自動除去 → 実装済み（要確認）

---

## 🟡 Phase 2: 設定UIの欠落

### F008: enable_memory_tools トグル追加
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/api/http/sections/chat.py` 設定パネルHTML (507-691行) |
| バックエンド | `ChatConfig.enable_memory_tools: bool`（既存、`service.py:52` で参照） |
| UI | 設定パネルにチェックボックス追加。`applyChatConfig()` で読み書き |

### F009: extract_max_tokens 入力欄追加
| 項目 | 内容 |
|------|------|
| ファイル | chat.py 設定パネル + `config/settings.py` |
| 現状 | `SummarizationConfig.llm_max_tokens: int = 500` のみ。`auto_extract` 用の `extract_max_tokens` は未定義 |
| 追加 | `ChatConfig.extract_max_tokens: int = 512` を settings.py に追加。chat.py の `auto_extract` 横に数値入力追加 |

### F010: 設定保存ボタン sticky footer化
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/api/http/sections/chat.py` CSS + HTML |
| 設計 | `#settings-panel` の下部に `position: sticky; bottom: 0` なフッター。Save/Cancelボタンを常時表示 |

---

## 🟠 Phase 3: UX改善

### F011: 設定パネル アコーディオン化
| 項目 | 内容 |
|------|------|
| ファイル | chat.py 設定パネルHTML (507-691行) |
| 設計 | 全10セクションを `<details><summary>` で折りたたみ。デフォルトで最初のセクションのみ開く |
| セクション | プロバイダー、モデル、APIキー、Temperature/MaxTokens、コンテキスト履歴、自動抽出、MCPサーバー、Skills、リフレクション、メンタルモデル、検索重み、サンドボックス |

### F012: リトライ/編集ボタン
| 項目 | 内容 |
|------|------|
| ファイル | chat.py JS |
| 設計 | 最後のアシスタント応答の横に 🔄 リトライボタン（同じ入力で再生成）。ユーザー入力バブルに ✏️ 編集ボタン（入力を `chat-input` に戻して再送） |

### F013: スラッシュコマンド
| 項目 | 内容 |
|------|------|
| ファイル | chat.py JS (chat-input の keydown イベント) |
| コマンド | `/memory <text>` → `memory_create` 発行、`/goal <text>` → `goal_create`、`/code <text>` → `execute_code` |
| 実装 | `chat-input` の `keydown` で `/` + Enter を検知。プレフィックスに応じてツール実行 |

### F014: デバッグモードトグル
| 項目 | 内容 |
|------|------|
| ファイル | chat.py 設定パネル + `config/settings.py` |
| 現状 | `log_level` で制御（`DEBUG`/`INFO` 等）。UI切替なし |
| 追加 | 設定パネルに `debug_mode: bool` トグル。`log_level` 連動 or 独立フラグ |

### F015: Alt+1〜9ショートカットにChatタブ追加
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/api/http/sections/base.py:863-869` |
| 現状 | Alt+1〜8 で overview〜admin の8タブ切替。Alt+9 未定義 |
| 変更 | tabs配列に `'chat'` 追加（Alt+9）。条件を `e.key >= '1' && e.key <= '9'` に |

### F016: 温度スライダー値初期表示修正
| 項目 | 内容 |
|------|------|
| ファイル | chat.py `applyChatConfig()` 関数 |
| 設計 | `applyChatConfig()` 内で温度スライダー `input[type="range"]` の value を明示的に設定 |

### F017: 添付ファイル表示ラベル復活
| 項目 | 内容 |
|------|------|
| ファイル | chat.py `chatSend()` 関数 (1420-1615行) |
| 現状 | chat.py:1462 で `CHAT.attachments` クリア前に入力表示。ファイル名が消える |
| 修正 | クリア前に `CHAT.attachments.length` を保存し、送信メッセージにファイル名表示 |

### F018: console.log → console.debug 置換
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/api/http/sections/chat.py` |
| 該当行 | 1012, 1016, 1582（3箇所） |
| 対応 | `console.log` → `console.debug` に置換 |

---

## 🔵 Phase 4: 新機能（高工数）

### F019: メモリパネルCRUD操作
| 項目 | 内容 |
|------|------|
| ファイル | chat.py JS (Memory Panel) |
| 設計 | 記憶カードにクリックイベント追加 → 編集モーダル（content/importance/tags編集）。削除ボタン。goal系カードに「完了」ボタン |

### F020: メモリタイムライン可視化
| 項目 | 内容 |
|------|------|
| ファイル | 新規: `memory_mcp/api/http/sections/timeline.py` |
| 設計 | vis-timeline を活用。感情色付き横軸タイムライン。21種感情色+絵文字対応。フィルタ（感情・タグ・重要度・件数）、クリックでslide-out詳細パネル |

### F021: スキルベースのシステムプロンプトテンプレート
| 項目 | 内容 |
|------|------|
| ファイル | chat.py 設定パネル |
| 設計 | `#chat-system-prompt` の上にドロップダウン。ビルトインプリセット + ユーザースキルから動的生成 |
| 状態 | 低優先度のため見送り。システムプロンプトは手動編集可 |

### F022: 音声入力 🎤
| 項目 | 内容 |
|------|------|
| 設計 | Web Speech API (`SpeechRecognition`)。chat-input横に🎤ボタン。認識結果をchat-inputに挿入 |

### F023: 会話エクスポート
| 項目 | 内容 |
|------|------|
| 設計 | チャット履歴をMarkdown/JSONでダウンロード。メッセージ一覧から生成。ダウンロードボタン追加 |

### F024: Web検索トグル
| 項目 | 内容 |
|------|------|
| 設計 | chat-input横に「🌐 Web検索」チェックボックス。ON時はシステムプロンプトにWeb検索指示追加 |

---

## 🟣 Phase 5: ツール不整合

### F025: MCP `memory` ツールの死にパラメータ削除
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/api/mcp/tools.py:159-260` |
| 削除対象 | `context_tags: list[str] | None`, `description: str | None`, `status: str | None` — シグネチャにあるが未使用 |
| 削除方法 | 関数シグネチャ + docstringから削除。呼出側が存在しないことを確認してから |

### F026: importance検証統一
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/api/mcp/tools.py:258-261, 308-311` |
| 現状 | create: 黙って clamp（`max(0.0, min(1.0, importance))`）。update: エラー返却 |
| 統一 | create も update と同様に「範囲外はエラー返却」に統一 |

### F027: builtin `memory_search` 結果上限を200に
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/application/chat/tools/builtin.py:83` |
| 現状 | `top_k = int(tool_input.get("top_k", 5)); ... min(top_k, 10)` — ハードキャップ10 |
| 変更 | `min(top_k, 10)` → `min(top_k, 200)`。definitions.py の `top_k` description も更新（1〜10 → 1〜200） |

### F028: builtinの感情検証追加
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/application/chat/tools/builtin.py:69-78` |
| 現状 | `memory_create` で `emotion_type` を検証せずDBに渡す |
| 追加 | `_VALID_EMOTIONS` をインポートし、`emotion_type` が有効値か検証。無効なら `"neutral"` にフォールバック |

### F029: `search_memory` の死に `mode` パラメータ削除
| 項目 | 内容 |
|------|------|
| ファイル | `memory_mcp/api/mcp/tools.py:622-650` |
| 現状 | `mode: str = "hybrid"` — 互換性のために残っているが内部では常にhybrid使用 |
| 削除 | 関数シグネチャ + docstringから `mode` 削除 |

---

## 🟢 sandbox 追加修正

### F030: sandboxコンテナ手動掃除（1回限り）
- NAS上で `sudo docker exec sandbox-docker docker rm -f sandbox-herta` 実行

### F031: NASデプロイ
- `docker-compose build --no-cache memory-mcp && docker-compose up -d`

---

# 大規模リファクタ（2026-05-16 夜〜）

## 🟣 Phase R1: フロントエンド 感情/身体状態表示修正（最重要）

### R1-1: メモリー一覧の感情表示強化
| 項目 | 内容 |
|------|------|
| 影響ファイル | `memory_mcp/api/http/sections/memories.py` |
| 現状 | コンパクト表示・カード表示とも `emotions` dict を完全無視。`emotion_type`（単一・旧形式）のみ参照 |
| 修正内容 | emotions dict がある場合は renderEmotionBars(emotions) を表示。なければ emotion_type にフォールバック |
| 行番号 | 517-527（compact）、549-558（card） |

### R1-2: メモリー一覧の身体状態完全表示
| 項目 | 内容 |
|------|------|
| 影響ファイル | `memory_mcp/api/http/sections/memories.py` |
| 現状 | コンパクト・カード表示とも fatigue と warmth のみ表示。arousal/heart_rate/pain は無視 |
| 修正内容 | renderBodyStateBars(body_state) を呼び出すよう統一。5指標すべて表示 |
| 行番号 | 517-527（compact）、549-558（card） |

### R1-3: グラフ詳細パネルへの感情・身体状態追加
| 項目 | 内容 |
|------|------|
| 影響ファイル | `memory_mcp/api/http/sections/knowledge_graph.py` |
| 現状 | openGraphDetailPanel(): key, content, tags, emotion_type, importance のみ。body_state/emotions 表示なし |
| 修正内容 | 詳細パネルに renderEmotionBars(data.emotions) + renderBodyStateBars(data.body_state) 追加 |
| 行番号 | 465-527 |

### R1-4: チャット メモリパネルへの感情・身体状態追加
| 項目 | 内容 |
|------|------|
| 影響ファイル | `memory_mcp/api/http/sections/chat.py` |
| 現状 | メモリパネル（検索結果・保存済みメモリ表示）に感情・身体状態の表示が一切ない |
| 修正内容 | memory-item-card に emotion + body_state 情報を追加。emotions dict から上位感情をバッジ表示、body_state 非ゼロ値があればコンパクト表示 |

### R1-5: 共通JS関数の重複除去
| 項目 | 内容 |
|------|------|
| 影響ファイル | `base.py`, `memories.py`, `knowledge_graph.py`, `overview.py`, `persona.py`, `chat.py` |
| 現状 | `renderEmotionBars()`, `renderBodyStateBars()`, `EMOTION_COLORS`, `BODY_BAR_COLORS` が base.py に定義済みだが、他のセクションで部分的に再定義・重複している |
| 修正内容 | base.py の共通関数を全セクションで使い回すよう統一。重複定義を削除 |

---

## 🟠 Phase R2: フロントエンド品質改善

### R2-1: 未表示フィールドの対応（表示 or 削除）
| 項目 | 内容 |
|------|------|
| バックエンドに存在するがフロントエンド未表示のフィールド | `access_count`, `last_accessed`, `summary_ref`, `equipped_items` |
| 判定 | `access_count`/`last_accessed`: メモリモーダルに追加表示（デバッグ情報として有用）。`summary_ref`/`equipped_items`: 内部管理用なので表示不要。 |

### R2-2: emotion フォールバックロジック統一
| 項目 | 内容 |
|------|------|
| 現状 | emotions dict があるのに emotion_type を表示している箇所が複数。`mem.emotion_type` という古いフィールド名と `mem.emotion` が混在 |
| 修正内容 | `emotions` dict > `emotion_type` > `emotion` の優先順位で表示するラッパー関数 `getEmotionDisplay(mem)` を作成し全箇所で統一 |

### R2-3: CSS重複・未使用スタイル削除
| 項目 | 内容 |
|------|------|
| 現状 | chat.py の CSS 590行が肥大。各セクションのインラインスタイルに重複多数 |
| 修正内容 | base.py の共通CSSに統合可能なものを抽出。未使用クラス・死にスタイルを削除 |

---

## 🔵 Phase R3: バックエンド品質改善

### R3-1: コード重複除去
| 項目 | 内容 |
|------|------|
| 重複① | `tools.py` と `builtin.py` で同じ引数バリデーション・エラー処理パターンを繰り返している |
| 重複② | `_VALID_EMOTIONS` が tools.py, builtin.py, emotion_validator.py の3箇所に定義 |
| 重複③ | `importance` の検証ロジックが tools.py 内で複数回出現 |
| 修正内容 | 共通バリデーションを `domain/memory/validators.py`（新規）に集約。`_VALID_EMOTIONS` を単一定義に統一 |

### R3-2: デッドコード除去
| 項目 | 内容 |
|------|------|
| 対象 | `tools.py` 内の未使用インポート、`builtin.py` の死にパラメータ、コメントアウトコード |
| 確認方法 | vulture/flake8 で未使用コード検出 |

### R3-3: 型アノテーション完全化
| 項目 | 内容 |
|------|------|
| 現状 | `dict`, `list` 等のジェネリック型が未パラメータ化の箇所多数 |
| 修正内容 | `dict[str, Any]`, `list[str]` 等に完全化。mypy strict で検証 |

---

## 🟢 Phase R4: テスト再構築

### R4-1: 削除するテストファイル
| ファイル | 理由 |
|---------|------|
| `test_placeholder.py` | セットアップ検証のみ。不要 |
| `test_dashboard_state_restore.py` | 1テストのみ。base.py のテストに統合 |

### R4-2: 統合するテストファイル（8→4）
| 統合元 | 統合先 | 理由 |
|--------|--------|------|
| `test_boost_recall.py` | `test_memory_service.py` | 同一ドメイン |
| `test_dashboard_goals_format.py` | `test_dashboard_e2e.py` | UIフォーマット |
| `test_chat_tab_controls.py` | `test_chat_service.py` | チャットUI |
| `test_normalize_emotion.py` | `test_memory_enricher.py` | 感情処理 |
| `test_clue_generator.py` | `test_search_engine.py` | 検索関連 |
| `test_memorag_search.py` | `test_search_engine.py` | 検索関連 |
| `test_migration_v006.py` | `test_migration_v009.py` | 旧マイグレーション |
| `test_migration_v008.py` | `test_migration_v009.py` | 旧マイグレーション |

### R4-3: 分割するテストファイル（3→8）
| 分割元 | 分割先 |
|--------|--------|
| `test_mcp_tools.py` | `test_mcp_memory_create.py`, `test_mcp_memory_read.py`, `test_mcp_search.py`, `test_mcp_context.py`, `test_mcp_items.py` |
| `test_goals_promises.py` | `test_goals.py`, `test_promises.py` |
| `test_summarization_worker.py` | `test_summarization.py`（一本化） |

### R4-4: 不足テストの追加
| ツール | 優先度 | 
|--------|--------|
| `goal_manage` MCPツール | 🔴 高 |
| `promise_manage` MCPツール | 🔴 高 |
| `sandbox` MCPツール | 🔴 高 |
| `sandbox_files` MCPツール | 🔴 高 |
| `invoke_skill` MCPツール | 🟡 中 |
| `item_history` MCPツール | 🟡 中 |

### R4-5: テスト品質改善
- `@pytest.mark.parametrize` を積極活用（現状1回のみ）
- `AsyncMock` を非同期関数に使用（現状 MagicMock で代用多数）
- 共通 fixture を `conftest.py` に集約
- In-Memory Repository パターンを標準化（モックより実体テスト優先）

---

## 非機能要件
- **機能破壊禁止**: MCPツール名・シグネチャ、HTTP APIエンドポイント・レスポンス形式、DBスキーマは変更しない
- **後方互換**: 既存クライアントが動作し続けること
- **テスト件数目標**: 現状988件 → 700〜800件（質は落とさず行数半減）
- **リファクタ範囲**: `memory_mcp/` 以下全ファイル。`scripts/` は対象外

---

# 実運用フィードバック修正（2026-05-17）

## 🔴 Phase A: 感情モデルロールバック（最重要）

### 背景
- commit 57f3734 で多次元感情（`emotions: dict[str, float]`）を導入したが、複雑すぎて実用に耐えない
- 単一感情タグ（`emotion: str`）+ 強度（`emotion_intensity: float`）に戻す
- 時間経過でニュートラルに減衰する仕様は維持

### A1: データモデル変更
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| Memoryエンティティ | `domain/memory/entities.py:22` | `emotions: dict[str, float] \| None` フィールド削除。`emotion: str` + `emotion_intensity: float` のみに |
| PersonaState | `domain/persona/entities.py:31-68` | `emotions: dict \| None` + `dominant_emotion`/`dominant_intensity` プロパティ削除。`emotion: str` + `emotion_intensity: float` に統一 |
| EmotionRecord | `domain/persona/entities.py:84-93` | `emotions: dict \| None` フィールド削除 |
| `compute_dominant_emotion()` | `domain/persona/entities.py` | 関数削除 |

### A2: DBマイグレーション
| 項目 | 内容 |
|------|------|
| 新規マイグレーション | `migration/versions/v021_remove_multi_emotions.py` |
| memories テーブル | `emotions TEXT` カラム削除 |
| emotion_history テーブル | `emotions TEXT` カラム削除 |
| 注意 | `emotion` (TEXT) + `emotion_intensity` (REAL) カラムは維持 |

### A3: 感情減衰の単一化
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| 減衰設定 | `domain/persona/emotion_decay.py` | 多次元各感情の半減期 → 単一 `EMOTION_HALF_LIFE`（デフォルト24h）に |
| `compute_emotion_decay()` | 同上 | 9次元個別計算 → 単一強度の指数減衰のみに |
| `apply_emotion_decay_if_needed()` | 同上 | `update_emotions()` → `update_emotion(name, intensity)` に変更。孤独感自動生成ロジックも削除 |

### A4: ツールシグネチャ変更
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| `_tool_memory_create` | `tools.py:152-190` | `emotions` パラメータ削除。`emotion` + `emotion_intensity` のみ |
| `_tool_memory_update` | `tools.py:192-270` | `emotions` パラメータ削除 |
| `_tool_update_context` | `tools.py:390-449` | `emotions` パラメータ削除。`emotion` + `emotion_intensity` のみ |
| MCPツールラッパー | `tools.py:917-1069` | `emotions` パラメータを全ツールから削除 |
| builtin handlers | `builtin.py:61-88, 123-148` | `emotions` 処理削除 |
| definitions.py | `definitions.py` | `emotions` スキーマフィールド削除 |
| `get_state_snapshot()` | `domain/persona/service.py:184-207` | 返り値から `emotions` dict 削除、`emotion`+`intensity` のみ |

### A5: WebUI表示変更
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| `renderEmotionBars()` | `base.py:705-726` | 削除（多次元表示用） |
| `EMOTION_BAR_COLORS` | `base.py:643-665` | 削除（多次元グラデーション用） |
| `renderEmotionBars` 呼出箇所 | `memories.py:845-865`, `knowledge_graph.py:511`, `base.py:973`, `timeline.py` | `renderEmotionBadges()` + `emotion_type` 単一表示に置換 |
| 感情検索フィルター | `memories.py:447-456` | 22感情ドロップダウンは維持（単一感情選択に使えるため） |
| アナリティクス感情グラフ | `analytics.py:46-47` | 単一感情時系列グラフに変更 |

---

## 🔴 Phase B: 身体状態減衰修正（最重要）

### B1: 減衰トリガー追加
| 項目 | 内容 |
|------|------|
| 問題 | `body_decay.py` の減衰は `get_context()` 呼出時のみ発火。WebUIダッシュボード閲覧では減衰しない |
| 修正 | `GET /api/dashboard/{persona}` および `GET /api/persona/{persona}` のレスポンス生成時にも `apply_body_decay_if_needed()` を呼ぶ |
| 影響ファイル | `api/http/routers/persona.py`, `api/http/routers/dashboard.py` |
| 補足 | 減衰ロジック自体（`body_decay.py`）は正しい。呼出箇所の追加のみ |

### B2: 減衰ワーカー追加（オプション）
| 項目 | 内容 |
|------|------|
| 新規 | `application/workers/state_decay_worker.py` |
| 設計 | 既存 `DecayWorker`（記憶忘却用）と同パターンの常駐デーモンスレッド |
| 間隔 | 設定 `state_decay_interval_seconds`（デフォルト300=5分） |
| 処理 | `apply_body_decay_if_needed()` + `apply_emotion_decay_if_needed()` を全ペルソナに対して実行 |
| 設定 | `config/settings.py` に `state_decay_interval_seconds: int = 300` 追加 |

---

## 🟡 Phase C: Goal/Promise ライフサイクル改善

### C1: 達成/取消時の長期記憶化
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| `_tool_goal_manage` achieve/cancel | `tools.py:767` | タグ変更に加え `importance = max(importance, 0.7)` に引き上げ、`tags.append("archived")` 追加 |
| `_tool_promise_manage` fulfill/cancel | `tools.py:810` | 同上 |
| 補足 | `context_note` に「🎯 goal X を達成しました / 取消しました」を自動追記 |

### C2: 安易なpromise追加の抑制
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| `_tool_promise_manage` create | `tools.py:787` | 作成時に `importance` が 0.5未満なら警告ログ出力し 0.5 にクランプ |
| definitions.py | `definitions.py:87-105` | promise_manage の description に「重要な約束のみ追加すること。単なるTODOは memory_create を使うこと」を明記 |
| builtin definitions | `definitions.py` | 同上 |

### C3: Context注入（既存の改善）
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| `_format_lightweight_response` | `tools.py:1414-1426` | アクティブgoal/promise の表示を現在の単純リストから、`importance` でソートし上位5件のみに（ノイズ削減） |
| chat pipeline | `prepare.py:222-238` | 同上の改善 |
| 表示形式 | — | `🎯 [goal] content（N分前）` の形式を維持 |

---

## 🟡 Phase D: WebUI Action 廃止

### D1: バックエンド削除
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| PersonaState | `domain/persona/entities.py:47` | `action_tag: str \| None` フィールド削除 |
| Memoryエンティティ | `domain/memory/entities.py:29` | `action_tag` フィールド削除（非推奨化済み） |
| PersonaService | `domain/persona/service.py:116` | `update_physical_state()` の allowed_keys から `action_tag` 削除 |
| MCP `_tool_update_context` | `tools.py:401, 437-438` | `action_tag` パラメータ削除 |
| MCP `update_context` wrapper | `tools.py:1028-1069` | `action_tag` パラメータ削除 |
| `get_context` stale clear | `tools.py:85-94` | action_tag の自動クリアロジック削除 |
| `get_context` formatting | `tools.py:1265-1266` | Action 行削除 |
| definitions.py | — | `action_tag` フィールド削除 |

### D2: フロントエンド削除
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| Overview タブ | `overview.py:363` | 🎬 Action バッジ表示削除 |
| Dashboard API | `persona.py:94` | action_tag の stats マージ削除 |

### D3: DB（マイグレーション不要）
- `action_tag` カラムは `memories` テーブルと `context_state` テーブルに残るが、コードから参照しなくなるため実質的に死にカラム
- 後日整理用マイグレーションで対応可能。今回のスコープ外

---

## 🔴 Phase E: Itemツール builtin対応

### E1: _MCP_SHARED_TOOLS 追加
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| `_MCP_SHARED_TOOLS` | `builtin.py:239-246` | `item_add`, `item_remove`, `item_equip`, `item_unequip`, `item_update`, `item_search`, `item_history` の7ツールを追加 |
| builtin definitions | `definitions.py` | 全itemツールが builtin tool list に含まれていることを確認（既存のはず） |

### E2: チャット装備欄実装
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| HTML プレースホルダー | `chat.py:653-658` | 現在空の `#memory-equipment-list` に装備情報をレンダリングするJS追加 |
| `updateMemoryPanel()` | `chat.py:1303-1384` | equipment 引数追加、装備スロット表示ロジック |
| SSE受信 | `chat.py:2102-2104` | InventoryUpdateSSE 受信時の `#memory-equipment-list` 更新処理追加 |
| バックエンド | `post.py:153-157` | InventoryUpdateSSE 生成は既存。フロントのみ対応 |

---

## 🟠 Phase F: Skills DB 定期更新

### F1: ファイル監視追加
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| 新規 | `application/workers/skills_watcher.py` | `watchdog` または簡易ポーリングで `data/skills/` ディレクトリを監視 |
| 設計 | watchdog利用不可なら簡易ポーリング（`threading.Timer` でN秒毎にglob） |
| 間隔 | 設定 `skills_sync_interval_seconds: int = 30` |
| 起動 | `main.py` の `lifespan` でスキル監視ワーカーを起動 |
| 変更検知時 | `SkillRepository.load_from_dir(skills_dir)` を呼び出しDB再同期 |
| 設定追加 | `config/settings.py` に `skills_sync_interval_seconds: int = 30` 追加 |

---

## 🟡 Phase G: 記憶リンク改善（身体状態）

### G1: Knowledge Graph 身体状態エッジ追加
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| Graph API | `api/http/routers/search.py:117-188` | `_build_graph()` に body_state 類似度エッジを追加 |
| 設計 | 同一ペルソナの記憶間で body_state の各次元（fatigue/warmth/arousal/heart_rate/pain）の差分 ≤ 0.15 のペアに `type: "body_state"` エッジ生成 |
| 色 | 身体状態エッジは緑系（`#34d399`）で表示 |

---

## 🟡 Phase H: WebUI メモリーカード表示改善

### H1: メモリー一覧カードに身体状態追加（確認と修正）
| 項目 | 内容 |
|------|------|
| 現状 | `renderBodyStateCompact()` が `memories.py:518, 544` で呼ばれているが、`bodyState[k] > 0` 条件のためニュートラル値（warmth=0.5, heart_rate=0.5）が表示されない |
| 修正 | `renderBodyStateCompact()` の条件を `bodyState[k] > 0` → `bodyState[k] != target_neutral` に変更。ニュートラルからの乖離があれば表示 |
| 影響 | `base.py:746-759` |

### H2: タイムライン詳細パネル確認
| 項目 | 内容 |
|------|------|
| 現状 | 探索結果では body_state bars が表示されている（`timeline.py:309-331`） |
| 対応 | 動作確認のみ。問題なければスキップ |

### H3: Graph詳細パネル確認
| 項目 | 内容 |
|------|------|
| 現状 | `knowledge_graph.py:516-520` で `renderBodyStateBars(data.body_state)` 呼出あり |
| 対応 | 動作確認のみ。問題なければスキップ |

---

## 🟢 Phase I: チャットUI改善

### I1: 操作ログ マウスオーバー詳細表示
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| HTML/CSS | `chat.py` | `.memory-tool-log` カードに `title` 属性追加（ツール名・パラメータ要約） |
| JS | `chat.py:2271-2287` | `handleMemoryToolResult()` で結果テキスト全文を tooltip データ属性に保存 |
| CSS | `chat.py` | `.memory-tool-log:hover::after` 疑似要素でツールチップ表示（最大300字） |

### I2: 🧠記憶活動にメンタルモデル表示
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| HTML | `chat.py:600-660` | メンタルモデルセクション追加（`#memory-mental-models-list`） |
| JS | `chat.py:1303-1384` | `updateMemoryPanel()` に mental_models 引数追加 |
| SSE | `chat.py:2102-2104` | `mental_model_done` イベント受信時にリスト更新 |
| バックエンド | `post.py:206-209` | `mental_model_done` SSE イベント送信（既存の可能性あり、確認） |

### I3: 🎯目標/🤝約束/🧩メンタルモデル追加時も💾保存された記憶に表示
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| JS | `chat.py:1303-1384` | `updateMemoryPanel()` で goals/promises/mental_models が追加された場合、それらを saved リストにも重複表示（タグバッジ付き） |
| 設計 | saved 配列に `{...goal, _source: "goal"}` のようにマークして、表示時に「🎯 目標として保存」等のラベル付与 |

### I4: ✨リフレクションの表示カテゴリ見直し
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| HTML | `chat.py:622-625` | セクションタイトルを「✨ リフレクション」→「✨ 洞察・リフレクション」に変更 |
| JS | `chat.py:1393-1404` | `updateReflectionPanel()` のカードを `memory-item-card` ではなく `insight-card` クラスに変更（記憶と視覚的に区別） |
| CSS | `chat.py` | `.insight-card` スタイル追加（破線ボーダー、イタリック体など記憶と異なる表現） |

---

## 🟢 Phase J: Speech 更新促進

### J1: get_context 時リマインド
| 変更箇所 | ファイル | 内容 |
|----------|----------|------|
| `_tool_get_context()` | `tools.py:54-141` | speech_style の最終更新から24時間以上経過していたら、context_note に「💬 speech_styleが{N}時間更新されていません。会話の調子に変化があれば update_context で更新してください」を追加 |
| `_format_lightweight_response()` | `tools.py` | speech_style の経過時間をコンテキストに注記（`💬 Speech: {style}（{N}時間前更新）`） |

---

## 非機能要件（本フェーズ）
- **DBマイグレーション**: A2（emotionsカラム削除）のみ必須。他は破壊的変更なし
- **後方互換**: MCPツールの `emotions` パラメータは削除されるが、使われていなければエラーにならない（Pydanticはデフォルトで未知フィールドを無視）
- **テスト**: 感情モデル変更に伴い関連テストの修正必須。新機能にはテスト追加
- **優先順位**: A → B → E → D → C → G → F → H → I → J

---

# 画像E2E（2026-06-08）

## 🔴 背景
- ユーザーがチャットに画像を添付しても、LLMにテキストパスしか送られず画像データが届かない
- LLMがMarkdownで画像URL/base64を出力しても、DOMPurifyが `<img>` を除去して表示されない
- Sandbox実行結果の画像（matplotlib等）は表示されているが、LLMテキスト応答中の画像は未対応

## 機能要件

### S1: ユーザー添付画像 → LLM送信
| 項目 | 内容 |
|------|------|
| フロント | `chatSend()` で画像添付時、`FileReader`でBase64に変換しメッセージに添付 |
| API | `POST /api/chat/{persona}` のbodyに `images: [{filename, mime_type, base64_data}]` 追加 |
| LLMメッセージ構築 | `pipeline/inference.py` で画像を `content_parts` に変換（既存のツール結果画像再送ロジックを流用） |
| プロバイダ対応 | OpenAI (`openai_compat.py` L77-84) + Anthropic (`anthropic.py` L66-88) 両対応（既存コードあり） |

### S2: LLMテキスト応答中の画像プレビュー
| 項目 | 内容 |
|------|------|
| DOMPurify | `safeMarkdown()` の許可タグに `img` を追加。属性: `src`, `alt`, `width`, `height` |
| Base64画像 | `data:image/...;base64,...` のインライン画像を自動検出し `<img>` で表示 |
| URL画像 | Markdownの `![alt](url)` → `<img>` 変換はmarked.jsで対応（DOMPurifyが通過すればOK） |
| スタイル | `max-width: 100%; border-radius: 8px; cursor: pointer;` クリックでメディアビューア表示 |

### S3: 添付ファイルプレビュー拡張（PDF・音声）
| 項目 | 内容 |
|------|------|
| PDF | 添付バッジクリック時、`<iframe src="..." width="100%" height="500">` でインラインプレビュー |
| 音声 | `audio/*` MIMEタイプの添付は `<audio controls>` で再生可能に |

## 変更ファイル
| ファイル | 変更内容 |
|----------|----------|
| `sections/chat.py` (JS) | `chatSend()`: 画像Base64変換 + メッセージ構築変更。`safeMarkdown()`: DOMPurify許可タグ追加。添付バッジ: PDF/音声プレビュー追加。メッセージレンダリング: `<img>` クリック→メディアビューア |
| `sections/chat.py` (CSS) | チャットメッセージ内画像・PDF iframe・音声プレイヤーのスタイル |
| `routers/chat.py` | `chat_endpoint()`: bodyに `images` フィールド追加（`List[ImageAttachment]`） |
| `application/chat/pipeline/inference.py` | ユーザー添付画像を `content_parts` に変換するロジック追加 |
| `domain/chat_config.py` または 新規モデル | `ImageAttachment` Pydanticモデル追加 |

## 非機能要件
- 画像サイズ上限: 10MB（フロント・バックエンド両方で検証）
- 対応画像形式: PNG, JPEG, GIF, WebP
- DOMPurifyの<img>許可は最小限（src/alt/width/heightのみ、onload等のイベントハンドラは不許可）

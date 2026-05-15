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
| ファイル | 新規: `memory_mcp/api/http/sections/timeline.py` または memories.py 拡張 |
| 設計 | vis-network 活用。感情色付き横軸タイムライン。記憶をカード/ノードとして配置 |

### F021: スキルベースのシステムプロンプトテンプレート
| 項目 | 内容 |
|------|------|
| ファイル | chat.py 設定パネル |
| 設計 | `#chat-system-prompt` の上にドロップダウン。ビルトインプリセット + ユーザースキルから動的生成 |

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

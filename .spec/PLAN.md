# PLAN - やりたいこと

## 2026-05-16 MCPツール統合 + コンテキスト最適化（ドッグフーディング後）

### 前提・方針決定
- **sandbox_image → sandbox_files 統合**: read操作で拡張子自動判別。ツール数削減。
- **ツール命名は Builtin flat スタイル**: `memory_create` > `memory(operation="create")`。LLM選択精度が段違い。
- **エンティティグラフ・矛盾検出・メンタルモデル・会話import**: LLMツールから外す。自動処理 or WebUI Adminのみ。
- **MCPツールのdocstring全般**: 300字キャップ。不要な説明を削る。
- **BuiltinとMCPの統合**: 同じコードベースで両方にツール提供。flat名で統一。

---

## 🔴 Phase 1: ツール統合・分割（高優先・今セッション）

### T001: sandbox_image → sandbox_files 統合
- `sandbox_files(operation="read", path=...)` に画像自動検出を統合
- PIL 読み取り + magic byte → content_base64 + content_type 返却
- `sandbox_image` ツール定義を削除（definitions.py + builtin.py）
- 削減: ~200 tokens

### T002: `memory` god-tool 分割
現状: 1ツール・21パラメータ・18サブオペレーション (2,096 tokens)

分割後（5ツール）:
- `memory_crud` — create, read, update, delete, history, stats (6 operation)
- `memory_block` — block_write, block_read, block_list, block_delete
- `memory_entity` — entity_search, entity_graph, entity_add_relation
- `memory_enrich` — enrich, check_contradictions
- `memory_housekeep` — refresh_context_snapshot, run_mental_model, import_conversation (Admin用)

...と思ったけどこれだとツール数が増える。ユーザーの「builtinのほうが使用率高い」という観点から、**flat名の単一目的ツール群** にする方がいい。

**最終形**（MCPツールとして直接登録）:
```
memory_create      — 記憶作成
memory_read        — 記憶読み取り
memory_update      — 記憶更新
memory_delete      — 記憶削除
memory_search      — 記憶検索（search_memory 統合）
memory_stats       — 統計取得
get_context        — コンテキスト取得（維持）
update_context     — 状態更新（維持、docstring圧縮）
item_add/remove/equip/unequip/search — 分割 or 維持？
sandbox            — コード実行（ファイル操作は sandbox_files に任せる）
sandbox_files      — ファイル操作 + 画像読み取り統合
goal_manage        — goal作成/達成/取消（operationパラメータ）
promise_manage     — promise作成/遂行/取消（operationパラメータ）
invoke_skill       — スキル実行
```
→ 約18ツール。各docstring 300字以内。総トークン ~2,700 → ~1,200。

### T003: goal/promise 6ツール→2ツール
- `goal_manage(operation, content, importance)` — create/achieve/cancel
- `promise_manage(operation, content, importance)` — create/fulfill/cancel
- 6ツール定義削除、2ツール追加
- 削減: ~216 tokens

### T004: エンティティ・矛盾・メンタルモデル・import を LLM ツールから削除
- MCPツールシグネチャから entity_*, check_contradictions, run_mental_model, import_conversation を削除
- entity抽出は memory_create 時に自動実行（既存）
- 矛盾検出は memory_create/update 時に自動チェック → reflection に記録
- メンタルモデルは自動トリガー（既存）
- 会話importは WebUI Import/Export タブのみ

---

## 🟡 Phase 2: docstring 圧縮（中優先）

### T005: 全ツール docstring ≤300字
| ツール | 現状 | 目標 | 削減 |
|--------|------|------|------|
| memory (god) | 3,820 | 分割で消滅 | 全量 |
| update_context | 1,892 | 300 | 1,592 |
| item | 893 | 300 | 593 |
| search_memory | 833 | 300 | 533 |
| sandbox | 921 | 300 | 621 |

### T006: update_context パラメータ集約
- `fatigue`, `warmth`, `arousal`, `heart_rate`, `touch_response` → `body_state: dict`
- `user_info`, `persona_info` は維持（構造化データのため）
- パラメータ数: 17 → 11

---

## 🟠 Phase 3: コード統合（中優先）

### T007: builtin.py と MCP tools.py の統合
- builtin.py の execute_tool() if/elif チェーンを削除
- ToolRegistry が MCP ツール関数を直接呼ぶように変更
- definitions.py は MCP ツールシグネチャから自動生成

### T008: MCP Server のツール登録を flat 名に
- 現在の `@mcp.tool()` 6関数 → flat 名の ~18関数に置換
- 内部実装は同じ domain service を呼ぶ
- 戻り値は dict 形式に統一

---

## 🔵 Phase 4: 自動化（低優先）

### T009: sandbox 自動クリーンアップ
- 7日以上前の `.py` ファイルを自動削除
- `.sandbox-pip-cache/` を file tree から除外

### T010: Goals/Promises 自動ハウスキーピング強化
- 閾値を10→5に下げる
- cancelled/achieved から30日経過したものを自動削除
- 日次要約ワーカーに組み込み

### T011: 日本語フォント対応
- sandbox に Noto CJK フォントをプリインストール
- matplotlib のデフォルトフォントを日本語対応に

---

## 🟢 NAS デプロイ（今すぐ）
- `docker-compose build --no-cache memory-mcp && docker-compose up -d`
- 本番に今回のWebUI修正（11ファイル・+372/-100行）を反映
- 動作確認: http://nas:26262

---

## メモ
- Builtin flat名の方がLLMのツール選択精度が高い（実績あり）
- MCP god-tool の operation パターンはコードのDRYには良いがLLMには悪い
- 「コードはDRY、インターフェースはflat」が最適解

---

## 2026-05-16（夜）: 大規模リファクタ【新フェーズ】

### 背景
- 多次元感情対応、auto-snapshot、body_state追加、get_context軽量化など
  短期間で大幅な仕様変更を重ねてきた
- バックエンドとフロントエンドで整合性が取れていない箇所がある
- 特にWebUIのメモリーカード表示で感情・身体状態が追従できていない
- テストが肥大化（59ファイル・988テスト・~13,000行）していてメンテ不能

### 目標
1. **全コードリファクタ**: バックエンドの重複除去・整合性整理
2. **WebUI 感情/身体状態 追従**: メモリーカード、チャットパネル、グラフ詳細など全表示箇所で emotions dict + body_state を完全表示
3. **テスト全削除 → 再作成**: 肥大化したテストをゼロから再構築。品質は落とさず、行数半減
4. **機能破壊禁止**: 外部インターフェース（MCPツール名・シグネチャ、HTTP APIエンドポイント）を変更しない

### 優先順位
1. バックエンドの重複コード・デッドコード除去
2. フロントエンドの感情/身体状態表示修正 ← **ユーザー指摘の最重要項目**
3. フロントエンドのコード重複・品質改善
4. テスト再構築

### 制約
- MCPツール名・シグネチャは変更不可（既存クライアント互換）
- HTTP APIエンドポイント・レスポンス形式は変更不可
- データベーススキーマは変更不可（マイグレーション不要）
- 機能を落とさないこと
- 時間無制限で品質最優先

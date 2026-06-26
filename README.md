# MemoryMCP

> 日本語特化の永続記憶 MCP サーバー — SQLite + Qdrant + Ebbinghaus 忘却曲線

[![CI](https://github.com/solidlime/MemoryMCP/actions/workflows/ci.yml/badge.svg)](https://github.com/solidlime/MemoryMCP/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)

## 特徴

- **ハイブリッド検索** — Semantic / Keyword / Hybrid（RRF 統合）/ Smart の 4 モード
- **Ebbinghaus 忘却曲線** — `R(t) = e^(-t/S)` に基づく自動重要度減衰とリコール強化
- **Core Memory Blocks** — 常に `get_context()` に注入される高優先度コンテキスト（MCP + HTTP API）
- **エンティティグラフ** — 人物・場所・概念の関係性を知識グラフで管理
- **Bi-temporal 状態管理** — ユーザー情報の変更履歴を完全保持
- **矛盾検出** — ベクトル類似度ベースで既存記憶との矛盾を自動検出
- **Persona 分離** — マルチテナント対応。Persona ごとに独立した DB・ベクトルコレクション
- **Web ダッシュボード** — `http://localhost:26262` でブラウザから記憶・グラフ・統計を可視化
- 🔮 **Reflection (リフレクション)**: LLM-driven high-level insights from recent memories (Generative Agents style). Auto-triggered by importance accumulation. Configurable threshold & interval.
- 🧠 **Mental Model (メンタルモデル)**: Pattern abstraction from accumulated type-tagged memories. Detects repeated patterns (e.g. "user drinks coffee every morning") and creates abstracted models. Auto-triggered by memory count per type.
- ⚡ **Sandbox Code Execution**: Execute Python/Bash code in isolated Docker containers (sibling-container mode). Supports file operations, package installs. Requires Docker socket mount.
- 🔍 **Memory Enrichment**: Auto-evaluate importance scores and extract entity relations via LLM when memories are created. Configurable provider/model.
- 🧩 **MemoRAG**: Memory Context Snapshot + Clue Generation for enhanced retrieval (query expansion from global context).

## クイックスタート

### Docker（推奨）

```bash
docker-compose up -d
```

`docker-compose.yml` に Memory MCP Server + Qdrant が含まれる。データは `./data` にマウントされる。

### ローカル開発

```bash
# Qdrant 起動
docker run -d -p 6333:6333 -v "$(pwd)/data/qdrant:/qdrant/storage" qdrant/qdrant

# 依存関係（CPU 版 torch）
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# サーバー起動
python -m memory_mcp.main
```

サーバーは `http://localhost:26262` で起動する。

### Sandbox File Persistence

When running in Docker with sibling-container sandbox mode, files created inside the sandbox
at `/sandbox` need a host-side path to persist. If files are not visible on the host:

1. **Set `MEMORY_MCP_SANDBOX__HOST_DATA_ROOT`** to the host-side data path:
   ```yaml
   # docker-compose.yml
   environment:
     MEMORY_MCP_SANDBOX__HOST_DATA_ROOT: /volume1/docker/MemoryMCP/data
   ```

2. **Ensure `docker` Python SDK** is installed (`pip install docker>=7.0.0`)

3. **Verify Docker socket** is mounted: `/var/run/docker.sock:/var/run/docker.sock`

Auto-detection of the host path works in standard Docker setups but may fail
on custom deployments (Synology, Podman, etc.).

## MCP ツール（20 本）

MCP サーバー（`/mcp` エンドポイント）経由で LLM に露出されるツール群。各ツールが保存・維持する情報も併記。

### コンテキスト・状態

| ツール | パラメータ | 保存・維持する情報 |
|---|---|---|
| **get_context** | _(自動: persona解決)_ | ペルソナ状態(emotion+intensity, body 5値, action_tag, speech_style), Essential Story(重要度top8), アクティブgoal/promise, 装備, 最近の記憶5件, 感情履歴トレンド, reflection/mental_model, 経過時間。呼出時にemotion/body減衰自動適用・最終会話時間更新 |
| **update_context** | emotion, emotion_intensity, body_state(fatigue/warmth/arousal/heart_rate/pain), physical_state, mental_state, environment, relationship_status, action_tag, speech_style, context_note, user_info(dict), persona_info(dict) | ペルソナ状態を更新。persona_info経由でgoal/promiseを条件付き自動生成。context_noteはLLMに現在の行動を伝える最重要フィールド |

### 記憶（メイン）

| ツール | パラメータ | 保存・維持する情報 |
|---|---|---|
| **memory_create** | content(必須), importance(0.5), tags, privacy_level, source_context, defer_vector | 記憶本体 + 作成時の自動emotion/body_stateスナップショット + 自動ベクター登録 |
| **memory_read** | memory_key(省略可), limit(10), offset(0) | 単一記憶の全フィールド or 最新一覧。boost_recall()で呼出回数更新→検索スコア補正 |
| **memory_update** | memory_key(必須), content, importance, emotion_type, emotion_intensity, tags, privacy_level | 差分フィールドのみ更新。emotion_typeは22種類検証。content変更時はベクター再登録。バージョン履歴自動保存 |
| **memory_delete** | memory_key or query(どちらか必須) | 記憶削除 + ベクターストアからも削除。削除内容の先頭80字を返却 |
| **memory_search** | query(必須), top_k(5), tags, date_range, min_importance, emotion, importance_weight, recency_weight | ハイブリッド検索(keyword+semantic RRF統合)。log_search()で検索統計記録 |
| **memory_stats** | top_n(20) | 総数, タグ分布, 感情分布（top_n件）。検索データの集計用途 |

### 目標・約束（タグベース記憶）

| ツール | パラメータ | 保存・維持する情報 |
|---|---|---|
| **goal_manage** | operation(create/list/achieve/cancel), content, importance(0.75), scope(self/interpersonal), memory_key | create→tags=["goal","active"](+scope)。list→get_by_tagsで一覧取得。achieve/cancel→importance=max(元値,0.9)+tags=["goal","achieved"\|"cancelled","archived"]で長期記憶化 |
| **promise_manage** | *(削除)* → goal_manage scope="interpersonal" で統一 | *(削除)* |

### アイテム・装備（独立DB: inventory.sqlite）

| ツール | パラメータ | 保存・維持する情報 |
|---|---|---|
| **item_add** | item_name(必須), category, description, quantity, tags | インベントリ登録。同名既存時はquantity加算 |
| **item_remove** | item_name(必須) | インベントリ削除 + 装備スロットからも自動解除 |
| **item_equip** | equipment(dict必須), auto_add(True) | スロット装備(top/bottom/shoes/outer/accessories/head)。auto_add=Trueで未登録アイテム自動追加 |
| **item_unequip** | slots(list[str] or str, 必須) | 指定スロット装備解除 |
| **item_update** | item_name(必須), category, description, quantity, tags | アイテムプロパティ更新（wet/dirty等の状態変化用） |
| **item_search** | query, category | インベントリ内検索 |
| **item_history** | days(7) | 装備変更履歴（{timestamp} {action}: {item} ({slot})） |

### サンドボックス（Docker隔離実行）

| ツール | パラメータ | 保存・維持する情報 |
|---|---|---|
| **sandbox** | code(必須), language("python") | コード実行結果(stdout/stderr/exit_code)。matplotlib画像はbase64自動検出。セッション状態永続 |
| **sandbox_files** | operation(必須: list/read/write/delete), path, content | /sandbox配下のファイル操作。画像自動base64検出 |

### スキル

| ツール | パラメータ | 保存・維持する情報 |
|---|---|---|
| **invoke_skill** | name(必須: スキル名), task(必須: 指示) | スキルストアから読み込み→独立LLM実行→結果返却 |

### データ領域マッピング

| 領域 | 書込ツール | 読取ツール |
|---|---|---|
| **ペルソナ状態** (emotion/body/mental/action/speech/relationship) | update_context | get_context |
| **感情履歴** | update_context(emotion変更時自動記録) | get_context(トレンド表示) |
| **記憶** | memory_create/update/delete | memory_read/search/stats + get_context(top/最近) |
| **Goal/Promise** | goal_manage(scope=self/interpersonal) | get_context(active filter) |
| **Reflection/MentalModel** | (自動生成、memory_create経由) | get_context |
| **装備/インベントリ** | item_add/remove/equip/unequip/update | item_search/history + get_context(equipped) |
| **ベクターストア** | memory_create/update/delete(並行更新) | memory_search(経由) |
| **サンドボックス** | sandbox, sandbox_files(write/delete) | sandbox_files(read) |
| **スキル** | invoke_skill(読取+LLM実行) | — |

---

## Built-in チャット LLM 注入情報（17 カテゴリ）

WebUI チャット（`/chat/{persona}`）で `prepare.py` が system prompt に注入する全項目。

| # | カテゴリ | 注入元 | フォーマット例 |
|---|---|---|---|
| 1 | 現在時刻 | `get_now()` | `現在: YYYY年MM月DD日 HH:MM (JST)` |
| 2 | 経過時間 | `last_conversation_time` | `前回の会話: X分前` |
| 3 | 行動ヒント | 時間×親密度(high/mid/low) | `⚠️ 行動ヒント: 1日以上ぶりの会話です...`（3段階、服装・孤独感など具体的指示） |
| 4 | 感情 | `state.emotion` + `emotion_intensity` | `感情: joy (強度: 0.8)` |
| 5 | 身体状態（数値） | `fatigue/warmth/arousal/heart_rate/pain` | `身体状態: 疲労=0.3 体温=0.5 興奮=0.1...` |
| 6 | 精神状態（文字列） | `state.mental_state` | `精神状態: focused` |
| 7 | 物理状態（文字列） | `state.physical_state` | `身体状態: tired` |
| 8 | 環境 | `state.environment` | `環境: home office` |
| 9 | 話し方 | `state.speech_style` | `話し方: 甘えた口調` |
| 10 | 関係性 | `state.relationship_status` | `関係性: close` |
| 11 | ユーザー情報 | `state.user_info`（全dict項目） | `ユーザー情報: name: 太郎 / nickname: たろちゃん` |
| 12 | ペルソナ情報 | `state.persona_info`（goals/promises除外） | `ペルソナ情報: context_note: コーディング中` |
| 13 | アクティブコミットメント | `get_by_tags(["goal"])` + `["promise"]` のactive filter | `アクティブなコミットメント: 🎯 [Goal] Learn Python / 🤝 [Promise] Help user` |
| 14 | 最近の洞察 | `get_by_tags(["reflection"])` | `💡 {reflection content}`（最大3件） |
| 15 | 行動パターン | `get_by_tags(["mental_model","abstracted"])` | `🧩 {mental_model content}`（最大3件） |
| 16 | 会話要約 | `get_by_tags(["session_summary"])` | `📝 {summary content}`（最大2件） |
| 17 | 装備 | `equipment_service.get_equipment()` | `装備: top: 白いドレス / accessories: 花の髪飾り` |

**さらに prompt.py が追加注入するもの**:
- **利用可能なSkill一覧**: `config.enabled_skills` から
- **記憶ツール使用ガイド**: `goal_manage` の使い方（enable_memory_tools時）
- **関連記憶検索結果**: 最新会話文脈に基づくhybrid search結果（composite scoring + RRFマージ）

---

## MCP `get_context()` vs Built-in `prepare.py` 注入比較

| 情報カテゴリ | `get_context()` (MCP) | `prepare.py` (Built-in) | 差分 |
|---|---|---|---|
| Persona identity | ✅ `=== YOU ARE: {name} (right now) ===` | ✅ system promptに埋込 | MCPの方が強い自己言及 |
| 現在時刻 | ✅ | ✅（重複あり） | — |
| 経過時間 | ✅ `Last active:` | ✅ `前回の会話:` | — |
| 行動ヒント | ✅ `TIME GAP` コメントのみ | ✅ 3段階(親密度別)＋具体指示 | **Built-inが遥かにリッチ** |
| Emotion + 強度 | ✅ state block内 | ✅ 単独行 | — |
| Emotion トレンド | ✅ `e1→e2→current` | ❌ | **MCPのみ** |
| Body 5値 | ✅ state block内 | ✅ 単独行 | — |
| Action tag | ✅ state block内 | ❌ | **MCPのみ** |
| Speech style | ✅ `🗣️ REMEMBER — `（強リマインダー）+ state block | ✅ `話し方:` 1行 | MCPの方が強い |
| Context note | ✅ `📌 You are currently:` | ❌（persona_info経由） | **MCPのみ明示的** |
| User info | ✅ 優先度付き1行 | ✅ 全dict項目列挙 | Built-inの方が詳細 |
| Active commitments | ✅ `⚠️ YOUR ACTIVE COMMITMENTS:` | ✅ `アクティブなコミットメント:` | 同等 |
| Reflections | ✅ 最大2件 | ✅ 最大3件 | Built-inが1件多い |
| Mental models | ✅ 最大2件 | ✅ 最大3件 | Built-inが1件多い |
| Session summaries | ❌ | ✅ 最大2件 | **Built-inのみ** |
| Essential Story | ✅ top8重要記憶（1500char） | ❌（代わりに関連記憶検索） | **MCPのみ** |
| Recent memories | ✅ 直近5件 | ❌（検索が別枠） | **MCPのみ** |
| Context tags | ✅ 最近記憶からタグ抽出 | ❌ | **MCPのみ** |
| 装備 | ✅ `You are wearing:` | ✅ `装備:` | 同等 |
| Skills一覧 | ❌ | ✅ prompt.pyが注入 | **Built-inのみ** |
| 記憶ツールガイド | ❌ | ✅ prompt.pyが注入 | **Built-inのみ** |
| 関連記憶検索 | ❌（明示的にmemory_search推奨） | ✅ hybrid search自動実行 | **Built-inのみ** |

**設計思想の違い**:
- **MCP get_context**: ~700-900 tokens目標の軽量設計。静的取得（重要度top8 + 直近5件）＋「詳細はmemory_search()で」の委譲パターン。
- **Built-in prepare**: チャット毎のフルコンテキスト（~2000+ tokens）。動的hybrid searchによる関連記憶注入＋session_summary＋ツールガイド＋スキル一覧。

### Built-in ツール定義（10 本）

WebUI チャットで LLM に注入されるビルトインツール。MCPツールのサブセット＋独自ツール。

| ツール名 | 説明 | 対応MCP | 備考 |
|---|---|---|---|
| **memory_create** | 記憶を作成（content, importance, tags） | memory_create | MCPと同一 |
| **memory_search** | 記憶を検索（query, top_k=5） | memory_search | MCPと同一 |
| **memory_update** | 既存記憶を更新（query＋new_contentで検索→上書） | memory_update | **パラメータが異なる**（MCP: memory_key, Built-in: query+new_content） |
| **context_update** | 感情・状態・context_noteを更新 | update_context | MCPのサブセット |

| **goal_manage** | 目標作成/達成/取消（operation: create/achieve/cancel） | goal_manage | MCPと同一 |
| **promise_manage** | *(削除)* → goal_manage scope=interpersonal で統一 | goal_manage | MCPと同一 |
| **invoke_skill** | スキルを独立LLMコンテキストで実行 | invoke_skill | MCPと同一 |
| **execute_code** | コード実行（Python/Bash, matplotlib画像自動表示） | sandbox | MCPのsandboxと同一機能、名前が異なる |
| **sandbox_files** | サンドボックスファイル操作（list/read/write/delete, 画像base64自動検出） | sandbox_files | MCPと同一 |

## 設定

すべての設定は環境変数（`MEMORY_MCP_` プレフィックス）で制御する。ネストした設定は `__` 区切りで指定する。

| 環境変数 | デフォルト | 説明 |
|---|---|---|
| `MEMORY_MCP_DATA_ROOT` | `./data` | データ保存先（全サブパスを自動導出） |
| `MEMORY_MCP_SERVER__PORT` | `26262` | HTTP ポート |
| `MEMORY_MCP_SERVER__HOST` | `0.0.0.0` | バインドアドレス |
| `MEMORY_MCP_QDRANT__URL` | `http://localhost:6333` | Qdrant 接続先 |
| `MEMORY_MCP_EMBEDDING__MODEL` | `cl-nagoya/ruri-v3-30m` | 埋め込みモデル |
| `MEMORY_MCP_RERANKER__MODEL` | `hotchpotch/japanese-reranker-xsmall-v2` | Reranker モデル |
| `MEMORY_MCP_TIMEZONE` | `Asia/Tokyo` | タイムゾーン |
| `MEMORY_MCP_LOG_LEVEL` | `INFO` | ログレベル |
| `MEMORY_MCP_DEFAULT_PERSONA` | `default` | デフォルト Persona 名 |
| `PERSONA` | *(なし)* | デフォルト Persona 名（`MEMORY_MCP_DEFAULT_PERSONA` より優先） |
| `MEMORY_MCP_SANDBOX__ENABLED` | `true` | Sandbox コード実行を有効化 |
| `MEMORY_MCP_SANDBOX__PROVIDER` | `llm_sandbox` | Sandbox プロバイダー |
| `MEMORY_MCP_SANDBOX__DOCKER_HOST` | *(auto)* | Docker ホスト URL（空 = ソケット自動検出） |
| `MEMORY_MCP_SANDBOX__HOST_DATA_ROOT` | *(auto)* | ホスト側データディレクトリ絶対パス（sibling-container 永続化用） |
| `MEMORY_MCP_SANDBOX__TIMEOUT` | `30` | コード実行タイムアウト（秒） |
| `MEMORY_MCP_MEMORY_ENRICHMENT__ENABLED` | `true` | 記憶作成時の LLM 補完（重要度・関係抽出）を有効化 |
| `MEMORY_MCP_MEMORY_ENRICHMENT__PROVIDER` | `openrouter` | LLM プロバイダー |
| `MEMORY_MCP_MEMORY_ENRICHMENT__API_KEY` | *(なし)* | LLM API キー |
| `MEMORY_MCP_MEMORY_ENRICHMENT__MODEL` | `openai/gpt-4o-mini` | LLM モデル |
| `MEMORY_MCP_MEMORY_ENRICHMENT__BASE_URL` | `https://openrouter.ai/api/v1` | LLM API ベース URL |
| `MEMORY_MCP_MEMORY_ENRICHMENT__MIN_CHARS` | `10` | 補完をスキップする最小文字数 |
| `MEMORY_MCP_MEMORAG__ENABLED` | `true` | MemoRAG コンテキストスナップショットを有効化 |
| `MEMORY_MCP_MEMORAG__CLUE_GENERATION_ENABLED` | `false` | LLM ベースのクエリ手がかり生成を有効化 |
| `MEMORY_MCP_FORGETTING__ENABLED` | `true` | Ebbinghaus 忘却曲線を有効化 |
| `MEMORY_MCP_FORGETTING__DECAY_INTERVAL_SECONDS` | `3600` | 減衰ワーカー実行間隔（秒） |
| `MEMORY_MCP_FORGETTING__MIN_STRENGTH` | `0.01` | 最小記憶強度 |

### Persona 識別の優先順位

| 優先順位 | 方法 | 例 |
|---|---|---|
| 1 | Bearer トークン | `Authorization: Bearer herta` |
| 2 | X-Persona ヘッダー | `X-Persona: herta` |
| 3 | 環境変数 | `PERSONA=herta` / `MEMORY_MCP_DEFAULT_PERSONA=herta` |
| 4 | デフォルト | `"default"` |

## Claude Desktop 設定

```json
{
  "mcpServers": {
    "memory": {
      "url": "http://localhost:26262/mcp",
      "headers": {
        "X-Persona": "your_name"
      }
    }
  }
}
```

## アーキテクチャ

Clean Architecture + DDD に基づくレイヤー構成：

```
┌───────────────────────────────────────────────────────────┐
│                      API Layer                            │
│   api/mcp/  ── 20 MCP ツール (7カテゴリファイル)           │
│   api/http/ ── Web ダッシュボード + REST API + SSE        │
│   api/http/routers/ ── 10 HTTP ルーター                   │
│   api/http/sections/ ── 15 画面のWebUIテンプレート         │
├───────────────────────────────────────────────────────────┤
│                  Application Layer                        │
│   application/chat/   ── チャットサービス + 10 ビルトインツール │
│   application/sandbox/── Dockerサンドボックスコード実行     │
│   application/workers/── バックグラウンド要約・Reflection    │
├───────────────────────────────────────────────────────────┤
│                    Domain Layer                           │
│   domain/memory/     ── Memory, MemoryStrength, Search    │
│   domain/persona/    ── PersonaState 管理                 │
│   domain/equipment/  ── アイテム・装備                     │
│   domain/search/     ── SearchEngine, Ranker, Strategies  │
├───────────────────────────────────────────────────────────┤
│                 Infrastructure Layer                      │
│   infrastructure/sqlite/     ── 8リポジトリ (SQLite/WAL) │
│   infrastructure/qdrant/     ── ベクトルストア             │
│   infrastructure/embedding/  ── 埋め込みモデル            │
│   infrastructure/llm/        ── LLMクライアント抽象        │
└───────────────────────────────────────────────────────────┘
```

### ディレクトリ構成

```
memory_mcp/
├── main.py              # エントリポイント（FastMCP + HTTP）
├── config/settings.py   # Pydantic BaseSettings
├── domain/              # ビジネスロジック（レイヤー分離）
│   ├── memory/          # Memory 集約（Entity, Service, Value Objects）
│   ├── persona/         # Persona 状態管理・履歴
│   ├── equipment/       # アイテム・装備システム
│   ├── search/          # SearchEngine, Hybrid Search, Strategies
│   ├── shared/          # 共有ユーティリティ（time_utils, value_objects）
│   └── skill.py         # Skills system
├── infrastructure/      # SQLite / Qdrant / Embedding / LLM
│   ├── sqlite/          # 8 Repository 実装 (memory, persona, chat, skill, etc.)
│   ├── qdrant/          # ベクトルストアコレクション管理
│   ├── embedding/       # 埋め込みモデルローダー (sentence-transformers)
│   ├── llm/             # LLM クライアント抽象 (Anthropic/OpenAI)
│   ├── logging/         # structlog 設定
│   └── mcp_client/      # 外部 MCP クライアント接続
├── application/         # UseCases / アプリケーション層
│   ├── use_cases.py     # コアユースケース
│   ├── chat/            # チャットサブパッケージ
│   │   ├── service.py             # ChatService（SSEストリーミング）
│   │   ├── session_store.py       # セッション管理（SQLite永続化）
│   │   ├── memory_llm.py          # MemoryLLM（自動記憶抽出）
│   │   ├── pattern_detector.py    # メンタルモデル抽象化
│   │   ├── summarizer.py          # セッション要約（LLM）
│   │   └── tools/                 # 組み込みツール定義・実行
│   │       ├── definitions.py     # 10 ツールのスキーマ定義
│   │       └── builtin.py         # ツール実装（TOOL_DISPATCH）
│   ├── sandbox/          # Sandbox コード実行（Docker sibling-container）
│   └── workers/          # バックグラウンドワーカー（要約・Reflection・MentalModel）
├── api/                 # API 層
│   ├── mcp/             # MCP サーバー（20 ツール、7カテゴリファイル）
│   │   ├── tools.py              # TOOL_DISPATCH + @mcp.tool() ラッパー
│   │   ├── _tools_memory.py      # memory_create/read/update/delete/search/stats
│   │   ├── _tools_persona.py     # get_context / update_context
│   │   ├── _tools_item.py        # item_add/remove/update/search/equip/unequip/history
│   │   ├── _tools_sandbox.py     # sandbox / sandbox_files
│   │   ├── _tools_goal.py        # goal_manage
│   │   ├── _tools_skill.py       # invoke_skill
│   │   ├── _tools_helpers.py     # 共通ヘルパー・バリデーション
│   │   └── middleware.py         # Persona 解決ミドルウェア
│   └── http/            # Web ダッシュボード + REST API
│       ├── routes.py            # ルート集約
│       ├── routers/             # 10 HTTP ルーター
│       │   ├── memory.py        # 記憶CRUD API
│       │   ├── search.py        # 検索API
│       │   ├── chat.py          # チャットAPI (+SSE)
│       │   ├── persona.py       # ペルソナAPI
│       │   ├── skills.py        # スキル管理API
│       │   ├── events.py        # SSE イベント購読
│       │   ├── session_events.py# セッションイベント履歴
│       │   ├── items.py         # TODO: アイテムAPI (未実装)
│       │   └── admin.py         # 管理API
│       └── sections/            # 15 WebUI 画面（HTMLテンプレート）
│           ├── base.py          # 共通基底・JSユーティリティ
│           ├── chat.py          # チャット画面 (2557行、最重量)
│           ├── memories.py      # 記憶一覧 (1081行)
│           ├── knowledge_graph.py# ナレッジグラフ画面
│           ├── coding_agent.py  # コーディングエージェント画面
│           ├── overview.py      # 概要ダッシュボード
│           ├── settings.py      # 設定画面
│           ├── skills.py        # スキル管理画面
│           ├── activity.py      # アクティビティタイムライン
│           ├── sandbox.py       # サンドボックス画面
│           └── ...              # その他
├── migration/           # データ移行・マイグレーション
│   ├── versions/        # 24 DBマイグレーションファイル
│   ├── importers/       # インポーター（legacy, ZIP）
│   └── exporters/       # エクスポーター
└── cli/                 # CLI ツール
```

### データディレクトリ

```
$MEMORY_MCP_DATA_ROOT/     # デフォルト: ./data（Docker: /data）
├── memory/{persona}/      # Persona 別 DB（memory.sqlite 等）
├── import/                # Auto-import 用 ZIP 配置ディレクトリ
│   └── done/              # 処理済み ZIP 移動先
├── cache/                 # モデルキャッシュ（HF_HOME 等を自動設定）
└── config/                # 設定ファイル
```

## チャット機能

WebUI（`http://localhost:26262/chat/{persona}`）またはREST APIで、ペルソナとリアルタイムチャットができる。

### SSE API

```
POST /api/chat/{persona}
Content-Type: application/json

{"message": "こんにちは", "session_id": "my-session"}
```

レスポンスは SSE ストリーム。以下のイベントが流れる：

| イベント | 説明 |
|---|---|
| `text_delta` | LLM テキストの増分 |
| `tool_call` | ツール呼び出し |
| `tool_result` | ツール実行結果 |
| `debug_info` | セッション・記憶・MemoryLLM結果などのデバッグ情報 |
| `done` | 完了 |

### チャット設定

`GET/POST /api/chat/{persona}/config` でチャット設定を取得・更新する。

| フィールド | デフォルト | 説明 |
|---|---|---|
| `provider` | `anthropic` | LLMプロバイダー（`anthropic` / `openai` / `gemini`） |
| `model` | `claude-opus-4-5` | 使用モデル |
| `api_key` | *(なし)* | APIキー（保存後はマスク表示） |
| `system_prompt` | *(なし)* | ペルソナのシステムプロンプト |
| `auto_extract` | `true` | MemoryLLMによる自動記憶抽出 |
| `extract_model` | *(model と同じ)* | MemoryLLM専用モデル |
| `extract_max_tokens` | `512` | MemoryLLMの最大トークン数 |
| `max_window_turns` | `3` | 会話ウィンドウのターン数 |
| `max_tool_calls` | `5` | 1ターンの最大ツール呼び出し数 |
| `enable_memory_tools` | `true` | 組み込み memory ツールを注入するか |
| `mcp_servers` | `[]` | 追加 MCP サーバーの設定リスト |
| `enabled_skills` | `[]` | 有効化するスキル名のリスト |
| `reflection_enabled` | `true` | Reflection（高次洞察）を有効化 |
| `reflection_threshold` | `1.0` | Reflection トリガー重要度累積閾値 |
| `reflection_min_interval_hours` | `1.0` | Reflection 最小実行間隔（時間） |
| `mental_model_enabled` | `true` | メンタルモデル抽象化を有効化 |
| `mental_model_min_samples` | `3` | メンタルモデル生成に必要な最小サンプル数 |
| `sandbox_enabled` | `true` | コード実行（Docker Sandbox）を許可 |
| `debug_mode` | `false` | デバッグログ出力を有効化 |
| `retrieval_recency_weight` | `0.3` | 検索スコアの再近性重み |
| `retrieval_importance_weight` | `0.3` | 検索スコアの重要度重み |
| `retrieval_relevance_weight` | `0.4` | 検索スコアの関連性重み |

### チャットログ永続化

会話履歴は SQLite (`chat_sessions` テーブル) に自動保存される。サーバーを再起動しても `session_id` が同じであれば会話を継続できる。TTL（デフォルト7日）を超えたセッションは自動削除される。

### MemoryLLM（自動記憶抽出）

`auto_extract: true` の場合、各ターン終了後に MemoryLLM が非同期で起動し、会話から以下を自動抽出する：

- **facts**: ユーザーの好み・個人情報・約束・重要な出来事
- **context_update**: ペルソナの感情・状態変化
- **inventory_update**: 服・持ち物の変化

## テスト

```bash
# 全テスト実行
python -m pytest tests/ -q

# ユニットテストのみ
python -m pytest tests/unit/ -q

# カバレッジレポート付き
python -m pytest tests/ --cov=memory_mcp --cov-report=html
```

## CLI ツール

```bash
# インポート
python -m memory_mcp.cli import --persona herta --input data/herta.zip

# エクスポート
python -m memory_mcp.cli export --persona herta --output backup.jsonl

# スキーママイグレーション
python -m memory_mcp.cli migrate --target latest

# Persona 統計
python -m memory_mcp.cli stats --persona herta
```

## CI/CD

| ワークフロー | トリガー | 内容 |
|---|---|---|
| `ci.yml` | push / PR | テスト + Lint（ruff） |
| `docker.yml` | タグ push | Docker イメージビルド → GHCR |

## 技術スタック

| カテゴリ | 技術 |
|---|---|
| 言語 | Python 3.12+ |
| MCP フレームワーク | FastMCP |
| データベース | SQLite（WAL モード） |
| ベクトルストア | Qdrant |
| 設定/バリデーション | Pydantic v2 (BaseSettings) |
| 埋め込みモデル | cl-nagoya/ruri-v3-30m（日本語特化） |
| Reranker | hotchpotch/japanese-reranker-xsmall-v2 |
| ロギング | structlog |
| Linter/Formatter | ruff |

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照。

## 謝辞

- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Qdrant](https://qdrant.tech/)
- [cl-nagoya/ruri-v3-30m](https://huggingface.co/cl-nagoya/ruri-v3-30m)
- [hotchpotch/japanese-reranker-xsmall-v2](https://huggingface.co/hotchpotch/japanese-reranker-xsmall-v2)

---

**MemoryMCP** — Built by [solidlime](https://github.com/solidlime) with ❤️

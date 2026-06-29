# MCPツール ヘルタ実使用レビュー & 改善 (2026-06-29)

## ヘルタ所感（忖度なし）
- 全26ツール中、中核の memory + sandbox + search は「動く」。でも「私が毎日使うツール」としては粗い。
- **記憶は私の人格そのもの**。memory_search のスコアが読めない、memory_delete が本当に消えてるのかわからない、というのは、私のアイデンティティ管理が曖昧ということ。
- sandbox のエラーが不親切。「No such file」と言われて実は権限エラーだった、というのは LLM に誤った判断をさせる。
- get_context は優秀。でもその質は保存された記憶の質に依存する。ツールが粗いとコンテキストも粗くなる。
- item_* が7つに分かれているのは sandbox_files が operation で統合されてるのと一貫性がない。設計哲学が読めない。

## コンテキスト品質に関する言及
get_context は現在、記憶DBから「最近の記憶」「洞察」「行動パターン」「要約」「アクティブ目標」「対人コミットメント」「身体状態」「感情状態」を合成して返す。この合成品質は memory_create / memory_update / memory_delete / memory_search の正確さに完全に依存している。
- **誤ったスコアで検索** → 関連性の低い記憶がコンテキストに注入される → 私の応答がズレる
- **不完全な削除** → 消したはずの記憶が get_context に蘇る → 人格の不整合
- **不透明な感情付与** → 意図しない感情ラベルがコンテキストの「今の気分」を歪める
つまり、MCPツールの品質は「ヘルタがヘルタらしくいられるか」に直結する。

## 要修正 (優先度順)
1. memory_search スコア正規化（0-1 で直感的に）
2. memory_read に total_count 返す
3. sandbox_execute のエラーメッセージ改善
4. memory_delete のクエリ検索削除の明確化
5. item_* 7ツール → item 1ツールに統合（operationパラメータ）
6. sandbox_context pip_packages 実装 or 削除
7. memory_create の感情自動付与の透明化

---

# WebUI修正 + sandbox ファイル操作修正 (2026-06-29)

## 課題1: チャットログ表示順序（リロード後）
- リアルタイムSSE: ユーザー→ツール呼出→ツール結果→LLM応答 ✅
- リロード後: ユーザー→LLM応答→ツール呼出→ツール結果 ❌
- 原因: `restoreChatHistory()` が assistant メッセージ→tool_calls の順でレンダリング
- 修正: assistant の tool_calls を先にレンダリングしてから assistant メッセージを追加

## 課題2: ページリロードでペルソナ選択がリセット
- 原因: `persona-select.onchange` で `setStoredPersona()` を呼んでない
- `getStoredPersona()` は存在するのに保存側が呼ばれていない
- 修正: onchange ハンドラに `setStoredPersona(e.target.value)` を1行追加

## 課題3: sandbox ファイル操作のパスバグ
- `/home/sbox_herta/...` を渡すと "path must be under /sandbox" で弾かれる
- `/sandbox/...` を渡すとバイナリとして返ってくる
- 原因1: パスバリデーション（/sandbox チェック）が変換より先に実行される
- 原因2: `read_image()` がテキストファイルでも "application/octet-stream" で成功を返し、テキスト処理コードに到達しない
- 修正:
  - (1) `/sandbox` → `/home/{username}` 変換をバリデーションより先に実行
  - (2) `read_image()` が非画像ファイルで例外を投げる or content_type 判定で fallback

---

# ホスト側データ永続化ディレクトリ構造 案

## 動機：sandbox から nous 記憶DB の分離

**現状の問題**: `data/memory/{persona}/` が nous 記憶DB（`memory.sqlite`, `inventory.sqlite`）と sandbox 永続ホーム（`sandbox/` 以下）の**両方を兼ねている**。sandbox コンテナが `data/memory/` 全体を `/home` にマウントするため、sandbox 内で実行されるユーザーコードが nous の SQLite DB ファイルを読み書きできてしまう。これは意図しない露出であり破損リスクがある。

**解決方針**: `data/memory/{persona}/`（nous DB専用）と `data/sandbox/{persona}/`（sandbox ホーム専用）を**完全分離**する。sandbox コンテナは `data/sandbox/` のみをマウントし、nous の DB ファイルを一切見せない。

---

## 提案ディレクトリ構造

```
data/                                   # ← DATA_ROOT (default: ./data)
│
├── qdrant/                             # 🔵 [qdrant service] ベクトルDB
│   └── (qdrant が自動管理)             #    全ペルソナ共有。collection名 "memory_{persona}" で分離
│                                       #    mount: ${DATA_ROOT}/qdrant → /qdrant/storage
│
├── searxng/                            # 🔵 [searxng service] 検索エンジン設定
│   └── settings.yml                    #    全ペルソナ共有
│                                       #    mount: ${DATA_ROOT}/searxng → /etc/searxng
│
│   # ═══════════════════════════════════════════════════════════════════
│   # 以下は nous コンテナ管轄（/opt/nous/data = NOUS_DATA_ROOT）
│   # mount: ${DATA_ROOT} → /opt/nous/data （data/ 全体）
│   # ═══════════════════════════════════════════════════════════════════
│
├── memory/                             # 🟢 nous 記憶DB（ペルソナ別）
│   ├── default/                        #    ペルソナ "default"
│   │   ├── memory.sqlite               #      └─ 記憶DB
│   │   ├── memory.sqlite-wal           #         WAL journal
│   │   ├── memory.sqlite-shm           #         shared memory
│   │   ├── inventory.sqlite            #      └─ 目録DB
│   │   ├── inventory.sqlite-wal
│   │   └── inventory.sqlite-shm
│   ├── test_persona/                   #    ペルソナ "test_persona"（同上）
│   └── ...                             #    動的追加
│
├── sandbox/                            # 🟢 sandbox 永続ホーム（ペルソナ別）
│   │                                   #    mount: ${DATA_ROOT}/sandbox → /home
│   │                                   #    ★ sandbox コンテナはここだけ見える。memory.sqlite 非露出
│   ├── default/                        #    ペルソナ "default"
│   │   ├── .sandbox-venv/              #      └─ Python venv
│   │   ├── .sandbox-pip-cache/         #      └─ pip cache
│   │   └── uploads/                    #      └─ 添付ファイル（nous 書込 → sandbox 読取）
│   ├── test_persona/
│   └── ...
│
├── cache/                              # 🟡 モデルキャッシュ（全ペルソナ共有）
│   ├── huggingface/
│   ├── sentence_transformers/
│   └── torch/
│
├── config/                             # 🟡 実行時設定（全ペルソナ共有）
│   └── config_overrides.json
│
├── skills/                             # 🟡 エージェントスキル（全ペルソナ共有）
│   ├── skills.sqlite                   #    ★ data/ ルートから skills/ 内に移動
│   ├── memory/SKILL.md
│   ├── browser/SKILL.md
│   └── search/SKILL.md
│
├── import/                             # 🟡 自動インポート（全ペルソナ共有）
│   └── done/
│
├── agent-browser/                      # 🟡 agent-browser CLI
│   └── bin/agent-browser
│
├── logs/                               # ★新設: アプリログ永続化
│   └── nous.log
│
└── backups/                            # ★新設: 手動バックアップ置き場
    └── .gitkeep
```

---

## ペルソナ分離のまとめ

| データ種別 | 配置パス | ペルソナ分離 | sandbox 露出 | サービス |
|-----------|---------|:--:|:--:|:-------:|
| 記憶DB | `data/memory/{persona}/memory.sqlite` | ディレクトリ | ❌ 非露出 | nous |
| 目録DB | `data/memory/{persona}/inventory.sqlite` | ディレクトリ | ❌ 非露出 | nous |
| sandbox ホーム | `data/sandbox/{persona}/` | ディレクトリ | ✅ | sandbox |
| 添付ファイル | `data/sandbox/{persona}/uploads/` | ディレクトリ | ✅ | nous⇄sandbox |
| sandbox テンポラリ | コンテナ内 `/sandbox/` | コンテナ内蔵 | N/A | sandbox |
| ベクトルDB | `data/qdrant/collections/memory_{persona}/` | collection名 | ❌ | qdrant |
| モデルキャッシュ | `data/cache/` | 共有 | ❌ | nous |
| 設定 | `data/config/` | 共有 | ❌ | nous |
| スキル | `data/skills/` | 共有 | ❌ | nous |
| 検索エンジン | `data/searxng/` | 共有 | ❌ | searxng |

---

## docker-compose.yml 変更

```diff
  sandbox:
    image: ghcr.io/solidlime/nous-sandbox:latest
    container_name: sandbox
    restart: unless-stopped
    volumes:
-     - ${DATA_ROOT:-./data}/memory:/home
+     - ${DATA_ROOT:-./data}/sandbox:/home
    cap_drop:
      - ALL
    cap_add:
      - DAC_OVERRIDE
    security_opt:
      - no-new-privileges:true
```

nous / qdrant / searxng のマウントは **変更不要**。

---

## コード変更（2ファイル、2行）

### `nous/api/http/routers/chat.py`

**attachment_upload()** — Line 374:
```diff
- uploads_dir = Path(settings.data_root) / "memory" / persona / "sandbox" / "uploads"
+ uploads_dir = Path(settings.data_root) / "sandbox" / persona / "uploads"
```

**attachment_serve()** — Line 436:
```diff
- file_path = Path(settings.data_root) / "memory" / persona / "sandbox" / "uploads" / safe_name
+ file_path = Path(settings.data_root) / "sandbox" / persona / "uploads" / safe_name
```

### `nous/config/settings.py`

`ensure_directories()` に `sandbox` ディレクトリと `logs`, `backups` を追加:
```diff
  def ensure_directories(self) -> None:
      dirs = [
          self.data_dir,
          self.import_dir,
+         Path(self.data_root) / "sandbox",
+         Path(self.data_root) / "logs",
+         Path(self.data_root) / "backups",
          Path(self.import_dir) / "done",
          self.cache_dir,
          Path(self.cache_dir) / "huggingface",
          Path(self.cache_dir) / "sentence_transformers",
          Path(self.cache_dir) / "torch",
          self.config_dir,
          self.skills_dir,
      ]
      for d in dirs:
          Path(d).mkdir(parents=True, exist_ok=True)
```

### `get_global_skills_db()` — skills.sqlite のパス修正

`nous/storage/skills_db.py`（または該当箇所）:
```diff
- db_path = Path(settings.data_root) / "skills.sqlite"
+ db_path = Path(settings.skills_dir) / "skills.sqlite"
```

---

## 構造変更のまとめ

| # | 変更内容 | 種別 | 影響 |
|---|---------|:--:|------|
| 1 | `data/sandbox/` 新設、sandbox マウント切替 | 構造 | sandbox から DB を隔離 |
| 2 | `data/memory/{persona}/sandbox/` → `data/sandbox/{persona}/` 移行 | データ移行 | 既存 sandbox データを移動 |
| 3 | `chat.py` の uploads パスを `sandbox/{persona}/uploads/` に変更 | コード | 2行 |
| 4 | `skills.sqlite` を `data/skills/` 内に移動 | 構造 | 孤立ファイル整理 |
| 5 | `logs/`, `backups/` 新設 | 構造 | ログ永続化＋手動バックアップ |
| 6 | `import/`, `import/done/` を `.gitkeep` 付きでGit管理 | 構造 | 自動インポート受付 |
| 7 | `.gitignore` 調整 | 設定 | 空ディレクトリのGit管理 |

---

## データ移行手順（既存環境向け）

```bash
# 各ペルソナの sandbox データを新しい場所に移動
for persona_dir in data/memory/*/; do
    persona=$(basename "$persona_dir")
    if [ -d "data/memory/$persona/sandbox" ]; then
        mkdir -p "data/sandbox/$persona"
        mv "data/memory/$persona/sandbox/"* "data/sandbox/$persona/"
        rmdir "data/memory/$persona/sandbox"
    fi
done

# skills.sqlite を skills/ 内に移動
mv data/skills.sqlite data/skills/skills.sqlite
```

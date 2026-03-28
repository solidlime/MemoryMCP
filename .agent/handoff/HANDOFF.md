# HANDOFF

## 最終作業: Goals/Promises タグ管理移行完了・CI全グリーン (2026-03-28)

### 背景
goals/promises を専用テーブルから memory+tag 方式に完全移行。v009マイグレーション追加・全ドキュメント更新・CI修正を完遂。

### 完了タスク

| コミット | 内容 |
|---------|------|
| `65aa3c8` | feat: migrate goals/promises to memory tag-based management |
| `0a6d8ae` | docs: goals/promises管理をmemoryタグ方式に全面更新 |
| `24fe2f9` | fix(lint): remove unused json import |
| `54c1b76` | fix(tests): integration tests for memory tag goals/promises |
| `304c729` | fix(tests): e2e counts for v009 |
| `491e0cc` | fix(importer): refresh memory count after persona_context import |
| `54637f8` | fix(tests): update herta memory counts to 167 after persona_context migration |

### 現状
- ✅ **CI #59: success** (Lint + Unit + Integration + E2E dogfood + Playwright)
- Unit: 371 tests passed
- Integration: 80 tests passed
- E2E dogfood: 75 tests passed (herta.zip: 167 memories)

### Goals/Promises 新設計
| type | status | 意味 |
|------|--------|------|
| goal | active | 進行中 |
| goal | achieved | 達成 |
| goal | cancelled | 中止 |
| promise | active | 有効 |
| promise | fulfilled | 達成 |
| promise | cancelled | 中止 |

MCPツールAPI:
- `update_context(append_goals=["..."])` → `memory(create, tags=["goal","active"])`
- `update_context(remove_goals=["..."])` → tags を `cancelled` に更新
- `get_context()` の ACTIVE COMMITMENTS → `get_by_tags(["goal","active"])` で取得

### 重要な実装詳細
- `LegacyImporter._import_persona_context()` が context.json の goals/promises を memories に INSERT OR IGNORE
- `import_from_dir()` 末尾で `SELECT COUNT(*) FROM memories` を再クエリして `counts["memories"]` を更新
- herta.zip: 165 (memories) + 2 (from context.json goals/promises) = **167**
- `test_auto_import.py` 全カウントを 167 に更新済み

### 次セッションでの注意点
- goals/promises テーブルは v009 で DROP済み。新規追加は memories + tags のみ
- `_import_goals`/`_import_promises` は silent 0 を返す（tables not found → exception catch）
- WebUI `/api/personas/{persona}/goals` は `get_by_tags(["goal"])` 全ステータス返却
- status icons: active=🔄, achieved/fulfilled=✅, cancelled=❌


### 背景
徹底的なコードレビューの依頼を受け、セキュリティ・品質・保守性の問題を14タスクに整理して全修正。

### 完了タスク一覧

| ID | 優先度 | 内容 | コミット |
|----|--------|------|--------|
| T01 | 🔴 CRITICAL | Zip Slip脆弱性修正（legacy_importer.py） | 6e812da |
| T02 | 🔴 CRITICAL | Bearer Token / X-Persona ヘッダー検証強化 | 6e812da |
| T03 | 🔴 CRITICAL | DBインデックス4本追加 + v007マイグレーション | 6e812da |
| T04 | 🟠 HIGH | routes.py 例外処理特定化 | 6e812da |
| T05 | 🟠 HIGH | HTTPクエリパラメータ型・範囲検証（5箇所） | 6e812da |
| T06 | 🟠 HIGH | DBトランザクション rollback追加（8メソッド） | 6e812da |
| T07 | 🟠 HIGH | セキュリティテスト23件追加 | 6e812da |
| T08 | 🟡 MEDIUM | MCP tools importance/top_k入力検証 | 6e812da |
| T09 | 🟡 MEDIUM | Pydanticリクエストモデル導入（CreateMemoryRequest等） | 6e812da |
| T10 | 🟡 MEDIUM | settings.py バリデーター追加（timezone/threshold/log_level） | 6e812da |
| T11 | 🟡 MEDIUM | 型ヒント確認（全関数→str付き済み） | — |
| T12 | 🟡 MEDIUM | 定数集約確認（既存OK） | — |
| T13 | 🟡 MEDIUM | memory_repo.py Mixin分割（block_repo.py, strength_repo.py） | 9ac8c78 |
| T14 | 🟡 MEDIUM | routes.py モジュール分割（routers/6ファイル + deps.py） | 6e812da |

### 主要変更ファイル

```
memory_mcp/
├── api/
│   ├── http/
│   │   ├── deps.py                      # 新規: 共有ヘルパー・Pydanticモデル
│   │   ├── routes.py                    # 12行の薄いラッパー（後方互換）
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── memory.py
│   │       ├── search.py
│   │       ├── persona.py
│   │       ├── item.py
│   │       └── admin.py
│   └── mcp/
│       ├── middleware.py               # Bearer/X-Persona バリデーション強化
│       └── tools.py                   # importance/top_k検証 + _VALID_EMOTIONS
├── config/settings.py                 # timezone/threshold/log_levelバリデーター
├── infrastructure/sqlite/
│   ├── connection.py                  # インデックス4本追加
│   ├── memory_repo.py                 # rollback追加 (604行に縮小)
│   ├── block_repo.py                  # 新規: SQLiteBlockMixin
│   └── strength_repo.py               # 新規: SQLiteStrengthMixin
├── migration/
│   ├── importers/legacy_importer.py   # Zip Slip修正
│   └── versions/v007_add_performance_indexes.py  # 新規
tests/unit/test_security.py            # 新規: 23テスト
```

### テスト状況
- **316 unit tests: 全PASS**
- セキュリティテスト23件: 全PASS
- コミット: `9ac8c78`, `6e812da` — 両方origin/mainにプッシュ済み

### 次セッションでの注意点
- T13のMixinパターン: `SQLiteMemoryRepository(SQLiteBlockMixin, SQLiteStrengthMixin)` — 継承順注意
- T14のrouters/: 各routerは `deps.py` の `_resolve_persona_from_request` / `_safe_get_context` に依存
- v007マイグレーションは既存DBに自動適用される（upgrade/downgrade両対応）
- `settings.py` の `ServerConfig.host = "0.0.0.0"` はDocker前提で意図的（コメント追記済み）

### 残課題（将来の改善候補）
- routes.py の `_resolve_persona_from_request` と middleware.py の二重実装（設計的統一）
- E2Eテスト（サーバー起動が必要、CI/CDで実施）

# SPEC: コード健全化 2026-06-26

## 1. sections/ のHTML外出し（最優先）

### 1.1 現状
`memory_mcp/api/http/sections/` の10ファイル（計6,986行）は、各Pythonクラス内でJinja2テンプレート文字列をハードコードし `self.render_section()` でレンダリングしている。HTML/CSS変更のたびにPythonコード修正が必要で、保守性が低い。

### 1.2 目標
- テンプレート文字列を `memory_mcp/templates/` 配下の `.html.j2` ファイルに抽出
- Python側はデータ準備（ビジネスロジック）のみ担当し、レンダリングは `self.render_template("template.html.j2", **context)` に委譲
- 既存の `render_section()` パターンとの互換性を保つ

### 1.3 対象ファイル（優先度順）
| # | ファイル | 現行数 | 目標行数 | 抽出テンプレート |
|---|---|---|---|---|
| 1 | `base.py` | 1,238 | ~400 | `base.html.j2` (共通レイアウト) |
| 2 | `memories.py` | 1,101 | ~350 | `memories.html.j2` |
| 3 | `settings.py` | 645 | ~250 | `settings.html.j2` |
| 4 | `coding_agent.py` | 634 | ~250 | `coding_agent.html.j2` |
| 5 | `knowledge_graph.py` | 606 | ~250 | `knowledge_graph.html.j2` |
| 6 | `overview.py` | 564 | ~200 | `overview.html.j2` |
| 7 | `chat.py` | 451 | ~150 | `chat.html.j2` |
| 8 | `activity.py` | 378 | ~150 | `activity.html.j2` |
| 9 | `timeline.py` | 361 | ~150 | `timeline.html.j2` |

### 1.4 制約
- 既存の全テスト（1,094件）がパスし続けること
- WebUIの表示・動作が変わらないこと
- テンプレートの読み込みは `render_section()` ベースクラスメソッドで透過的に行う
- テンプレートパス: `memory_mcp/templates/sections/{name}.html.j2`

### 1.5 テンプレート構造
```
memory_mcp/templates/
├── sections/
│   ├── base.html.j2          # 共通レイアウト（ヘッダー・ナビ・フッター）
│   ├── memories.html.j2      # メモリー一覧・詳細
│   ├── settings.html.j2      # 設定画面
│   ├── coding_agent.html.j2  # コーディングエージェント
│   ├── knowledge_graph.html.j2
│   ├── overview.html.j2
│   ├── chat.html.j2
│   ├── activity.html.j2
│   └── timeline.html.j2
├── partials/
│   ├── modal.html.j2         # 共通モーダル
│   ├── pagination.html.j2    # ページネーション
│   └── ...
```

---

## 2. TODO.md 棚卸し

### 2.1 現状
`.spec/TODO.md` の全タスクが `[ ]`（未チェック）。実装済みの画像生成・PDF解析タスクも未チェックのまま。

### 2.2 やること
- フェーズ1（画像生成基盤）: 全サブタスク → `[x]` に
- フェーズ2（PDF解析）: 全サブタスク → `[x]` に
- フェーズ3（テスト・検証）:
  - `3.1.1 test_image_gen_providers.py` → `[x]`
  - `3.1.2 test_read_pdf.py` → `[x]`
  - `3.1.3 test_chat_service.py` → 確認して更新
  - 3.2, 3.3, 3.4 は実装状況を確認して更新
- 新セクション「コード健全化」をTODO末尾に追加

---

## 3. カバレッジ 62% → 70%

### 3.1 方針
- まず現在のカバレッジレポートを取得し、未カバーのホットスポットを特定
- `api/http/sections/` はテンプレート外出し後のためスキップ
- `application/` と `domain/` レイヤーを中心にテスト追加
- テストしやすい純粋関数・バリデーションロジックを優先

### 3.2 制約
- 既存テストを壊さない
- モック可能な外部依存はモックする

---

## 4. pre-commit/lefthook 統一

### 4.1 現状
- `.pre-commit-config.yaml`: ruff lint + ruff format
- `lefthook.yml`: ruff format + ruff check（同一内容）

### 4.2 決定
- **lefthook に統一する**（シンプル・Node.js不要・CIとの親和性）
- `.pre-commit-config.yaml` を削除
- 必要に応じて `.git/hooks/pre-commit` の既存シンボリックリンク/コピーをクリーンアップ

---

## 5. Dependabot ブランチ整理

### 5.1 現状
リモートに10本の放置 dependabot ブランチ:
```
dependabot/github_actions/actions/checkout-7
dependabot/github_actions/codecov/codecov-action-7
dependabot/github_actions/docker/build-push-action-7
dependabot/github_actions/docker/login-action-4
dependabot/github_actions/docker/metadata-action-6
dependabot/pip/dev-dependencies-a63b452107
dependabot/pip/ml-dependencies-a7024e8e54
dependabot/pip/numpy-gte-2.4.4
dependabot/pip/pydantic-settings-gte-2.14.1
dependabot/pip/sentencepiece-gte-0.2.1
```

### 5.2 やること
- CIパス可能なものはマージ
- コンフリクト・テスト失敗するものはクローズ
- ローカルでは `git push origin --delete <branch>` で削除

# KNOWLEDGE: 全体評価・対策・教訓 2026-06-28 (v6)

## 評価から得た重要な知見

### ツール設計のアンチパターン（検出済み）
1. **「何でもツール」**: 1ツールに複数アクションを詰め込む（browser, sandbox_files）
2. **「双子ツール」**: 同一スキーマで説明文だけ違う（goal_manage/promise_manage）
3. **「破壊的更新」**: 曖昧検索→無言上書き（memory_update）
4. **「隠れた制限」**: 制限値がLLMに伝わらない（read_pdf等）
5. **「スキーマと実装の不一致」**: required不整合（sandbox_files）
6. **「長文description」**: LLMのツール選択精度低下

### 類似プロジェクト比較
- memstate-mcp: 7ツール、neuromcp: 検索品質◎、isaacriehm: supersede安全更新、Anthropic公式: 9ツールシンプル、danielsimonjr: 213ツールは反面教師

### 設計原則
1. 1機能1ツール 2. ツール数10前後 3. description1行 4. 制限値はLLMに見せる 5. 破壊的操作は2段階 6. required一致

### UI/UX アンチパターン（新規検出）🆕
1. **「発見不可能な高機能」**: スラッシュコマンド・ショートカットが一切UI表示されず、ソースコードを見た人しか知り得ない
2. **「沈黙の空状態」**: データ0件時に完全白紙。初回利用者に「何をすればいいか」の手がかりゼロ
3. **「CSSの断片化」**: Pythonヒアドキュメントに300行超のインラインスタイルが分散。CSSファイルが唯一のスタイルソースではない
4. **「ハードコードテーマ値」**: `rgba(255,255,255,0.06)` 等の固定値がテーマ変数を迂回し、ライト/ダーク切替を破綻させる
5. **「重複定義の放置」**: scrollbar スタイルが 2回定義され、先行定義がデッドコード化

### テストアーキテクチャの知見
- テスト0件の重要ファイル: memory_llm.py (571行), builtin.py handler 4件 (390行), definitions.py (309行)
- テスト0件の改修対象では、**必ずテストを先行作成してから実装に入る**
- 全grepで見つからない非文字列一致（JS変数名、HTML id、SSEフィールド名）の見落としに注意
- chat.js (1735行) はJSテストフレームワーク未導入のため手動確認のみ

### CSS保守性の教訓 🆕
- Pythonヒアドキュメント内の `style="..."` は grep で一括検索・置換が困難
- テーマ変数（`var(--glass-bg)`）で定義しつつ、実装では生の rgba 値を使う「二重管理」が破綻を生む
- `<style>` ブロックを HTML sections に書くと、読み込み順序の保証がなく予測困難

## 既存知見（継承）
- sections/ のJS/CSS静的ファイル分離完了（6,986→2,770行）
- 画像生成: DALL-E 3 + SD 両対応、base64統一
- PDF解析: PyMuPDF + pdfplumber + OCR (tesseract)
- pre-commit: lefthook に統一済み
- カバレッジ: 63→65%、長期目標70%

## emotion trigger_key 即時活用（2026-07-01）
- `update_emotion()` は `trigger_key` と `context` パラメータを持つが、全4呼出箇所で `None` 渡しだった（因果関係の喪失）
- 修正: 各呼出に `context` を設定（manual_update, llm_suggested, time_decay）
- 感情トレンド表示にコンテキスト情報を追記: `joy → sadness(time_decay) → anger(manual_update)`
- `memory_llm.py` はLLM提案の感情変更 → `context="llm_suggested"`（現時点ではtrigger_memory_keyなし）
- `emotion_decay.py` は時間減衰 → `context="time_decay"`（trigger_memory_keyは恒久的にNone）
- 教訓: DBスキーマにあってもコード経路でデータが流れていないパターンが多い。oracle audit で検出可能。

## read_pdf パス解決（2026-07-01）
- Nous は Docker 2コンテナ構成（nous + sandbox）で sandbox ファイルは別コンテナの `/home/sbox_*/` に存在
- `read_pdf` は nous コンテナ内の `Path.exists()` でチェック → sandbox パスは常に存在しないと判定
- 修正: `/home/sbox_*` / `/sandbox` で始まるパスを sandbox session 経由で読み取り、bytes で PyMuPDF に渡す
- `_sync_process_pdf` は `str | bytes` を受け付けるよう拡張。`fitz.open(stream=bytes, filetype="pdf")` で in-memory 処理
- エラーメッセージを日本語→英語に統一（既存の他ツール英文化と一貫）

## sandbox 単一コンテナ移行の知見 🆕

### 技術的教訓
- `llm_sandbox` のマルチコンテナ管理は複雑性が高く、単一コンテナ + `docker exec` 方式で十分なユーザー分離が可能
- `docker.from_env().containers.get("sandbox").exec_run(code, user=username)` でLinuxユーザー権限分離がシンプルに実現できる
- `DAC_OVERRIDE` ケーパビリティ追加で、ユーザー所有でないファイルの読み取りが可能（sandbox共有に必要）

### 実装パターン
- ユーザー管理は純粋関数（コマンドリスト生成）と Docker 実行（副作用）を分離する設計がテスト容易性を高める
- `user_manager.py`: 純粋関数 → ユニットテスト容易
- `service.py`: Docker exec 実行 → 統合テスト/モックテスト
- `_execute_via_file()`: ヒアドキュメント → ファイル → 実行 → クリーンアップ パターンでシェルインジェクション防止

### 改名の原則
- パッケージ名変更は段階的に: (1) ファイルシステム (mv), (2) Pythonインポート (sed), (3) 文字列リテラル (fixer並列)
- 並列fixerで効率的だが、同一ファイルの競合に注意（今回は競合なし）
- テストの env var 文字列は grep から漏れやすいので別途 sed で対応

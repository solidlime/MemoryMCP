# KNOWLEDGE: コード健全化 2026-06-26

## 技術的知見

### sections/ のJS/CSS静的ファイル分離
- **base.py**: Jinja2は使われておらず、全HTML/JSが raw Python文字列 + 文字列連結。全セクションは独立した `render_<name>_tab()` / `render_<name>_js()` 関数
- **JS抽出パターン**: 各 `render_<name>_js()` のJS内容を `static/<name>.js` に抽出し、関数を `return _JS`（モジュールレベル定数で読込）に変更。関数シグネチャは変えない（dashboard.py連携のため）
- **CSS抽出パターン**: `render_head()` のインラインCSS(540行) を `static/base.css` に抽出し `<link>` タグで参照。base.js も同様に `<script src>` 化
- **dashboard.py非依存**: 各sectionはdashboard.pyから呼ばれるため、関数シグネチャ（`() -> str`）は不変
- 結果: sections/ 6,986→2,770行（-60%）、全テスト1,147件パス維持

### カバレッジ改善
- 外部依存のないピュアロジック（pattern_detector, use_cases, compress, runtime_config）を優先
- sandbox, LLM呼び出し, Docker依存コードはカバレッジ向上困難
- 短期目標: 63%→65%。70%は長期目標（インフラ層のテストがボトルネック）

### pre-commit/lefthook 統一
- lefthook に一本化、`.pre-commit-config.yaml` を削除
- lefthook.yml は ruff format + ruff check 両方設定済みで変更不要

### 評価知見
- **セクション肥大化が最大の負債**: PythonファイルにHTML/JS/CSS文字列埋め込みは保守性・可読性を著しく損なう。静的ファイル分離で大幅改善
- **TODO管理の形骸化**: SDD導入後も運用が追いつかず、実装済みタスクが未チェックのまま放置
- **カバレッジ62%は最低限**: CIのゲートとしては機能するが、品質指標としての価値は低い

## 既存知見（継承）

### 画像生成
- DALL-E 3 API: `openai.images.generate(model="dall-e-3", prompt=..., size="1024x1024", quality="standard", n=1)`
- SD WebUI API: `POST /sdapi/v1/txt2img {prompt, negative_prompt, steps, width, height}`
- 戻り値は base64 に統一

### PDF解析
- PyMuPDF (fitz) + pdfplumber の組み合わせ
- fitz でテキスト＋画像、pdfplumber でテーブル

### DBマイグレーション
- チャット設定テーブルに新カラム追加パターン: v025 searxng と同じ

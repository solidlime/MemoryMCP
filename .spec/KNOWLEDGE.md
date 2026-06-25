# KNOWLEDGE: マルチモーダルLLM対応

## 技術的知見

### 画像生成
- DALL-E 3 API: `openai.images.generate(model="dall-e-3", prompt=..., size="1024x1024", quality="standard", n=1)` → `{data: [{url, revised_prompt}]}`
- SD WebUI API: `POST /sdapi/v1/txt2img {prompt, negative_prompt, steps, width, height}` → `{images: ["base64..."], parameters: {...}}`
- 戻り値は base64 に統一（SDはbase64そのまま、DALL-EはURLからダウンロード→base64化）
- 画像データは大きいので `tool_result_max_chars` の制限にかからないよう truncate 戦略を工夫する必要あり

### PDF解析
- PyMuPDF (fitz): `fitz.open(path)` → `page.get_text()` / `page.get_images()` / 画像抽出
- pdfplumber: `pdfplumber.open(path)` → `page.extract_tables()` / `page.extract_text()`
- fitz のテキスト抽出は高速だがレイアウト情報なし。pdfplumber はレイアウト保持するが遅い
- 組み合わせ: fitz でテキスト＋画像、pdfplumber でテーブル
- 大規模PDF対策: ページ数・テキスト長に上限設定

### テスト
- Qdrantはモックで十分（既存の `mock_qdrant` fixture を流用）
- DALL-E/SD APIは httpx モックで模擬応答
- PDFテスト用 fixture: 2ページのサンプルPDFをプログラム生成（fitz で簡単に作れる）
- agent-browser の戻り値は自動JSONシリアライズ → `JSON.stringify()` すると二重エンコードになるので注意（MEMORY.mdの既存教訓）

### DBマイグレーション
- チャット設定テーブルに新カラム追加パターン（v025 searxng と同じ）:
  1. `migration/versions/v026_image_gen.py` 作成
  2. `migration/versions/__init__.py` に登録
  3. `chat_config.py` の `save()` に `ALTER TABLE ADD COLUMN IF NOT EXISTS` 追加
  4. 移行ファイルはスキップされても `save()` の動的追加でカバー

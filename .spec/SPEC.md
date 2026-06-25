# SPEC: マルチモーダルLLM対応

## 1. 画像生成ツール

### 1.1 概要
チャット内でLLMが `image_generate` ツールを呼び出し、DALL-E 3 または自前 Stable Diffusion サーバー経由で画像を生成。生成画像はbase64で返却されチャットログ内に表示。

### 1.2 プロバイダ対応
| プロバイダ | 実装 | API |
|---|---|---|
| OpenAI (DALL-E 3) | `infrastructure/image_gen/dalle.py` | `openai.images.generate()` |
| Stability (SD WebUI) | `infrastructure/image_gen/stability.py` | `POST /sdapi/v1/txt2img` |

共通インターフェース: `infrastructure/image_gen/base.py` — `ImageGenProvider` 抽象クラス

### 1.3 ツール定義
```python
# ツール名: image_generate
# パラメータ:
#   prompt: str (必須) — 生成プロンプト
#   size: str = "1024x1024" — 画像サイズ (DALL-E: 1024x1024/1792x1024/1024x1792, SD: 任意)
#   quality: str = "standard" — DALL-Eのみ "standard"|"hd"
#   n: int = 1 — 生成枚数 (1-4)
#   provider: str = "auto" — "openai"|"stability"|"auto" (auto=設定に従う)
# 戻り値: {images: [{base64: str, revised_prompt: str, size: str}], provider: str}
```

### 1.4 ChatConfig 追加フィールド
```python
image_gen_enabled: bool = False
image_gen_provider: str = "openai"  # "openai" | "stability"
image_gen_dalle_model: str = "dall-e-3"  # "dall-e-3" | "dall-e-2"
image_gen_stability_url: str = ""  # SD WebUI API エンドポイント (例: http://localhost:7860)
```

### 1.5 SSEイベント
| イベント | type | 内容 |
|---|---|---|
| 生成開始 | `image_gen_start` | `{provider: str, prompt: str, n: int}` |
| 生成完了 | `image_gen_result` | `{images: [{base64, revised_prompt}], provider: str}` |

### 1.6 フロントエンド表示
- チャットログ内に生成画像を `<img>` で表示
- クリックでメディアビューア展開
- 生成中はプレースホルダー（スピナー）表示

### 1.7 チャット設定UI
- 基本設定アコーディオン内に「画像生成」セクション追加
- 有効/無効トグル
- プロバイダ選択（OpenAI / Stability）
- DALL-E モデル選択（dalle_enabled時）
- SD URL入力（stability_enabled時）

---

## 2. PDF/ドキュメント解析

### 2.1 概要
チャットに添付されたPDFをLLMが `read_pdf` ツールで解析。テキスト・テーブル・埋め込み画像を抽出し構造化データとして返却。

### 2.2 ツール定義
```python
# ツール名: read_pdf
# パラメータ:
#   path: str (必須) — ワークスペース内のPDFパス
# 戻り値:
#   {
#     filename: str,
#     pages: int,
#     text: str,  # 全ページテキスト
#     tables: [{page: int, headers: [str], rows: [[str]]}],
#     images: [{page: int, base64: str, mime_type: str}]  # 最大5枚まで
#   }
```

### 2.3 実装
- `memory_mcp/application/chat/tools/builtin.py` に `_handle_read_pdf()` 追加
- `definitions.py` の `_BUILTIN_DISPATCH` に登録
- 依存ライブラリ: `PyMuPDF` (fitz), `pdfplumber`
- テキスト: fitz でページ単位抽出
- テーブル: pdfplumber で抽出（構造化）
- 画像: fitz で埋め込み画像を抽出（最大5枚、1MB/枚上限）

### 2.4 フロー
1. ユーザーがPDFをドラッグ＆ドロップ → 添付バッジ表示（既存機能）
2. `chatSend()` がファイルをアップロード → サーバーがワークスペースに保存
3. メッセージに `[添付ファイル: workspace/path/to/file.pdf]` が含まれる
4. LLMが `read_pdf(path="workspace/path/to/file.pdf")` を呼び出す
5. 抽出結果をLLMが処理 → 応答を生成

### 2.5 制限
- ファイルサイズ上限: 50MB（ChatConfigに追加）
- 抽出テキスト上限: 100,000文字（超えた場合はtruncate）
- 画像抽出上限: 5枚, 1枚あたり1MB

---

## 3. 共通事項

### 3.1 実装ファイル構成
```
memory_mcp/
├── infrastructure/
│   └── image_gen/          # 新規
│       ├── __init__.py
│       ├── base.py          # ImageGenProvider 抽象クラス
│       ├── dalle.py         # DALL-E 3 実装
│       ├── stability.py     # SD WebUI 実装
│       └── factory.py       # get_image_gen_provider()
├── application/
│   └── chat/
│       ├── events.py        # +ImageGenStartSSE, ImageGenResultSSE
│       ├── tools/
│       │   ├── definitions.py   # +image_generate, +read_pdf
│       │   └── builtin.py       # +_handle_image_generate(), +_handle_read_pdf()
│       └── chat_service.py
├── domain/
│   └── chat_config.py      # +image_gen フィールド, +pdf_max_size
├── api/
│   └── http/
│       ├── sections/chat.py # +画像生成設定UI
│       ├── static/chat.js   # +image_gen イベントハンドリング, +生成画像表示
│       └── static/chat.css  # +生成画像スタイル
└── tests/
    └── unit/
        ├── test_image_gen_providers.py  # 新規
        ├── test_read_pdf.py             # 新規
        └── test_chat_service.py         # 更新
```

### 3.2 依存パッケージ（requirements.txt 追加）
- `PyMuPDF>=1.24.0` — PDF解析
- `pdfplumber>=0.11.0` — テーブル抽出
- `openai>=1.30.0` — DALL-E API（既存の可能性あり）

### 3.3 DBマイグレーション
- chat_config テーブルに image_gen 系カラム追加（新規マイグレーションファイル v026）

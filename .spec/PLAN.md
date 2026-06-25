# PLAN: マルチモーダルLLM対応

## 背景
MemoryMCPのチャット機能は画像入力（Vision）対応済みだが、画像生成・PDF解析が未対応。
ユーザーは以下のマルチモーダル拡張を希望。

## 要件サマリー

### 1. 画像生成ツール
- DALL-E 3 と Stable Diffusion 両方をサポート
- プロバイダ設定で切り替え可能
- チャットツールとして実装（LLMが必要に応じて `image_generate` を呼ぶ）
- ヘルタの表情を会話内容に沿って生成できるように（LLMがプロンプトを生成→画像出力）
- 生成画像はチャットログ内に表示

### 2. PDF/ドキュメント解析
- テキスト抽出 + テーブル構造 + 埋め込み画像も抽出
- 添付されたPDFをLLMが解析できるように
- ツールとして実装（LLMが `read_pdf` 等を呼んで内容を取得）

## 優先度
1. 画像生成（DALL-E → SDの順）
2. PDF解析

## 技術スタック候補
- DALL-E: openai パッケージ（既存のOpenAICompatProviderと共用？別ツール化？）
- Stable Diffusion: Replicate / Stability AI API / HuggingFace Inference
- PDF: PyMuPDF (fitz) + pdfplumber（テーブル用）

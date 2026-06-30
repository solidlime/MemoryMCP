# SPEC v3 — SillyTavern採用 + Dynamic Temperature + ペルソナ可視化 + 音声 (2026-07-01)

> **位置づけ**: 本SPECは既存 `.spec/SPEC.md` (Phase 0-3, レビュー対策) の続編。
> **完了済み前提**: R01-R09全タスク (T01-T14), emotion_decay 体験層化, autoCapture, storage abstraction

## 変更履歴
- v1: 初版 (SillyTavern調査ベース)
- v2: oracle レビュー反映 (コスト制御、データフロー修正、過剰設計削減)
- v3: ComfyUI本格調査 + Irodori-TTS調査反映、Phase E 新設

---

## 背景

Nous は「日本語AIエージェントのための永続記憶MCPサーバー」として十分な基盤を持つ。emotion_decay で感情の時間減衰を計算し、TIME GAP で時間経過を体験層で表現できるようになった。しかし **ペルソナの「生きた感覚」はまだ不足**している。

3つの追加次元でペルソナに生命を吹き込む:
1. **Dynamic Temperature** — 感情が推論の温度を揺らす
2. **動的ペルソナ画像生成** — コンテキストに応じてペルソナの「姿」が変わる（ComfyUI ローカル）
3. **音声対話** — Irodori-TTS (MIT) で感情表現豊かな日本語音声

---

## Phase A: Dynamic Temperature — 情緒の揺らぎ [最優先]

### A0: 前提確認

**現状**: `ChatConfig.temperature` 固定 0.7。`LLMProvider.stream(temperature=config.temperature)` で全プロバイダに渡される。
**感情状態**: `PersonaState.emotion` + `emotion_intensity` は既に decay 後で取得可能。

### 要件

- **RA01**: `EmotionDrivenSampler` ドメイン層クラス (`nous/domain/sampling.py`)
  - `compute(base_temp, emotion, intensity) → effective_temp`
  - 感情別モディファイア: anger=+0.15, sadness=-0.10, joy=+0.05, excitement=+0.20, neutral=±0.0 等
  - `intensity` でモディファイアをスケール (`modifier * intensity`)
  - clamp: [0.1, 1.8]

- **RA02**: `ChatConfig` 拡張
  - `dynamic_temperature: bool = True`
  - `emotion_temperature_scale: float = 0.2`
  - `top_p: float | None = None` (新規、LLM provider に渡す)

- **RA03**: Pipeline orchestrator が `PersonaService.get_context()` → `EmotionDrivenSampler.compute()` → `effective_temp` を `InferenceStep` に注入
  - **設計判断 (oracle)**: `InferenceStep` は `PersonaState` を直接参照しない。パイプラインオーケストレータが事前計算し、`effective_temp` だけ渡す。純粋。
  - `InferenceStep.run()` のシグネチャに `temperature` 引数が既にあるので、ChatConfig から読む代わりに effective_temp を受け取る

- **RA04**: WebUI設定追加
  - チャット設定パネル「Core」セクションに Dynamic Temperature 切替 + スケールスライダー + top_p 追加

---

## Phase B: ペルソナ画像生成 — LLM-driven ツール呼出 + ペルソナ自動合成 [最重要]

### B0: 前提確認

**既存image_gen**: `StabilityProvider` (A1111 API, deprecated) + `DalleProvider` (OpenAI API, $0.04-0.08/枚)
**ペルソナ外見**: 現状 `PersonaState` に `description` (外見記述) フィールドなし → **追加必須**
**感情マッピング**: 28 GoEmotions ラベルは過剰。既存の感情文字列 (`anger`, `joy`, `sadness`, `neutral`) で十分。

### 設計思想 (パパの指示反映)

**2つの経路**:

1. **LLM-driven (主)**: LLM が `persona_portrait(scene="海辺で夕日を見ている")` を自発的に呼ぶ
   → Nous がペルソナの外見・感情・装備を**自動注入**してプロンプト合成
   → 「ペルソナが海辺にいる姿」が生成される

2. **Auto-generate (副)**: 感情変化時 etc. に背景自動生成 (RB03 参照)

**核**: LLM はシーン・状況だけを指定。ペルソナの姿は Nous が裏で補完する。

### 技術選定

**選定**: ComfyUI (clsferguson/comfyui-docker, GHCR配布, CUDA 12.8, SageAttention自動キャッシュ)
- REST + WebSocket API。`/prompt` POST → `/history/{id}` GET の fire-and-forget パターンで十分。
- Python クライアント: `comfy-api-simplified` (MCPサーバ同梱, v1.6.0)
- アニメモデル: Animagine XL 4.0 (SDXL base, 日本語キャラ名対応, `1girl, {char_name}, ...` 形式)
- ライセンス: ComfyUI GPL-3.0 (バックエンド利用は問題なし)、Animagine XL 4.0 は OpenRAIL++M 由来

**非選定**: 
- Diffusers: Python 内蔵でシンプルだが OOM/キュー管理を自前実装必要。Phase B.5 として後日検討。
- A1111: deprecated (wiki 2023-09-09 以降未更新)

### B0.5: クリティカル前提 — コスト制御レイヤー (oracle 指摘)

**oracle 判定**: 「コスト制御なしで実装した場合、ユーザーが気づかないうちにAPI費用が膨らむ。設計欠陥」
**対応**: **デフォルト完全OFF**。ユーザーが明示的に有効化するまで1枚も生成しない。

```python
class PortraitGenerationConfig(BaseModel):
    enabled: bool = False                          # デフォルトOFF
    provider: Literal["comfyui", "openai", "stability"] = "comfyui"
    comfyui_url: str = "http://localhost:8188"      # ComfyUI API (別PC/Docker可)
    auto_generate: bool = False                    # 自動生成もデフォルトOFF
    generate_interval_min: int = 10                # 最低10分間隔
    size: str = "512x512"                          # プレビュー用小型
    quality: str = "standard"
    emotion_threshold: float = 0.3                 # 強度変化閾値
    max_monthly_budget: float = 5.0                # 月額上限ドル (ComfyUIなら0)
```

### 要件

- **RB01**: ペルソナ外見記述の格納場所
  - `PersonaState` に `appearance: str` フィールド追加 (髪色・瞳・服装・年齢・特徴の自由記述)
  - persona_info dict の `appearance` キーから自動読み込み
  - 未設定時: 感情アイコンのみ表示（画像生成しない）

- **RB02**: `PortraitPromptBuilder` (`nous/domain/persona/portrait_prompt.py`)
  - **2つの合成モード**:
    1. **LLM合成**: LLM が指定した scene 記述 + ペルソナ外見 + 感情 = 完全プロンプト
    2. **自動合成**: 感情/身体状態/直近状況のみ = 簡易ポートレート
  - 入力: `persona: PersonaState`, `scene: str | None`, `emotion`, `intensity`, `body_state`, `equipment`
  - 出力: Animagine XL 4.0 プロンプト (`1girl, {char_name}, ...`)
  - **LLM合成テンプレート** (scene あり):
    ```
    1girl, {char_name}, original, {emotion_adj} expression,
    {appearance_desc}, {equipment_desc},
    {scene},  ← LLMが指定した状況
    masterpiece, high score, great score, absurdres
    ```
  - **自動合成テンプレート** (scene なし):
    ```
    1girl, {char_name}, original, {emotion_adj} expression,
    {appearance_desc}, {body_state_desc},
    looking at viewer,
    masterpiece, high score, great score, absurdres
    ```
  - 感情→形容詞マッピング: joy="smiling", anger="glaring", sadness="teary", neutral="calm", curiosity="inquisitive" 等

- **RB03**: `PortraitGenerationService` (アプリケーション層)
  - **LLM-driven**: MCP ツールから呼ばれて `PromptBuilder(scene=llm_scene)` → ComfyUI → 画像返却
  - **Auto-generate**: 感情変化時 etc. の背景生成 (デフォルトOFF)
  - レート制限 (interval_min)
  - 感情変化閾値チェック (emotion_threshold, 自動生成時のみ)
  - プロンプトhashキャッシュ
  - 生成失敗時のフォールバック (感情カラーアイコン)
  - 最終生成時刻・生成回数カウンタ (月額予算管理)

- **RB04**: ComfyUI ImageGenProvider 追加 (`nous/infrastructure/image_gen/comfyui.py`)
  - `comfy-api-simplified` 依存
  - ワークフロー JSON 管理: `models/persona_portrait.json` を基本テンプレート
  - Animagine XL 4.0 のモデルロードは ComfyUI 側で常時 warmup (Docker 起動時にロード)
  - 512x512 → 30 steps → Euler Ancestral → CFG 5.0
  - negative_prompt: Animagine 公式推奨値

- **RB05**: 既存 `image_gen` モジュールとポートレート生成の設定分離
  - `ChatConfig.image_gen_*` はチャット中ツール呼出用 (変更なし)
  - `PortraitGenerationConfig` はペルソナポートレート用 (新設、独立)
  - ComfyUI URL は両方で共有可だが provider/サイズ/品質は別設定

- **RB06**: MCP ツール `persona_portrait` (LLM-driven 核) 🆕
  - LLM が `persona_portrait(scene="海辺で夕日を見ている", style="anime")` を呼ぶ
  - `scene` 記述 + ペルソナ情報を `PortraitPromptBuilder` で合成
  - `PortraitGenerationService` → ComfyUI → 生成画像を返す
  - 戻り値: base64 画像 + revised_prompt
  - **これが Phase B のメイン経路**

- **RB07**: WebUI — ペルソナ画像表示
  - Overview タブ: 最新生成画像 + 「Generate Now」ボタン (scene 入力可)
  - チャットタブ: 右サイドバー上段に最新画像表示
  - 画像生成中: スケルトン + パルスアニメーション
  - 画像なし/未設定: 既存の感情カラーアイコン
  - 自動生成設定パネル (interval, threshold, enabled)

- **RB08**: SSE イベント
  - `portrait.generate_start` → 生成開始通知
  - `portrait.generate_complete` → 生成完了 + base64 (SSE でフロントに通知)
  - `portrait.generate_error` → エラー通知

- **RB09**: ComfyUI 接続設定
  - **外部サービス前提**: ComfyUI は別 PC / 別 Docker で稼働。Nous からは HTTP API (`:8188`) で接続
  - healthcheck: `/system_stats` エンドポイントで死活監視
  - ComfyUI 非起動時: 感情アイコンにフォールバック（エラーにはしない）
  - 推奨環境: NVIDIA GPU 8GB+ VRAM、Animagine XL 4.0 プリロード
  - **セキュリティ**: ComfyUI に認証なし → LAN 内運用 or リバースプロキシが必須

- **RB10**: プロンプト安全フィルタ
  - 長さ制限 (512 char)
  - 禁止ワードフィルタ (NSFW, violent)
  - LLM シーン記述のバリデーション (injection 対策)

---

## Phase C: WebUI ペルソナ投影のリアルタイム化

- **RC01**: SSE イベント拡張
  - `emotion_change` — 感情変更時に発行 (PersonaService.update_emotion)
  - `body_state_change` — 身体状態変更時に発行 (PersonaService.update_physical_state)
  - `portrait.updated` — ポートレート更新時に発行

- **RC02**: フロントエンド SSE ハンドラ
  - `base.js` の EventSource で上記イベントをリッスン
  - 感情バー、身体バー、ペルソナ画像の動的更新

---

## Phase D: SillyTavern 機能採用 (選択的, 縮小)

### D1: Lorebook 風キーワード記憶 → Phase E に降格
**oracle 判定**: Qdrant ハイブリッド検索が既に同等以上。二重管理になるため過剰設計。

### D2: Author's Note 風常時注入
- `persona.author_note: str | None` フィールド追加 (自由記述)
- 挿入位置: system prompt の末尾 (before messages)
- Frequency 制御: 常時・N回に1回・感情変化時のみ (3段階)
- **工数: 小**

### D3: ペルソナ PNG メタデータ埋め込み (Persona Card V2/V3 互換)
- PNG tEXt チャンクの `ccv3` keyword に JSON (base64) を格納
- 埋め込み内容: name, appearance, emotion, body_state, equipment, portrait_prompt
- import/export: WebUI の Import/Export タブに「Download Persona Card」ボタン
- SillyTavern との相互運用 (キャラカードとして読み込める)
- **工数: 中**

---

## Phase E: Voice AI — Irodori-TTS 統合 [新設]

### 技術選定

**選定**: **Irodori-TTS** (500M-v3 / 600M-v3-VoiceDesign, MIT, 日本語特化)
- Flow Matching + Diffusion Transformer (VITS系ではない)
- OpenAI TTS API 完全互換 → Nous 側は極薄ラッパーで済む
- 感情制御: 絵文字 (emoji-based) + キャプション (caption-based) + 参照音声 (reference)
- Docker: 公式 compose.yaml (GPU/CPU/ROCm)
- 品質: timbre 0.9745 (6モデル中最高)、MOS 4.37
- 弱点: 漢字読み精度、20-30s チャンク制限、seed 不安定性、若いプロジェクト (4ヶ月, 開発者1名)

**非選定**:
- Style-Bert-VITS2: AGPL-3.0 (ライセンス汚染リスク)
- VOICEVOX: 商用制約、感情制御が弱い
- AivisSpeech: 独自ライセンス (LGPLベース)、VOICEVOX同様

### 要件

- **RE01**: Irodori-TTS 接続設定
  - **外部サービス前提**: Irodori-TTS-Server は別 PC (GPU 8GB+) で稼働。Nous からは OpenAI 互換 API (`:8088/v1`) で接続
  - **NAS 非推奨**: Synology NAS (24GB RAM) では GPU がないため CPU 推論のみ。Flow Matching 拡散モデルは CPU だと RTF 3-5 (20秒音声→1分以上)。チャット対話には非実用的
  - `irodori_url` 設定で外部 URL を指定
  - GPU モード: NVIDIA RTX 3060 12GB 以上推奨 (RTF ~0.5)
  - CPU モード: テキスト量が少なければバッチ処理用に一応使える
  - 非起動時: 音声なしで動作継続（エラーにはしない）

- **RE02**: VoiceEngine 抽象 + 感情→音声変換 (`nous/infrastructure/voice/`)
  - `base.py`: `VoiceEngine` ABC (tts, list_voices, register_voice)
  - `irodori.py`: Irodori-TTS OpenAI 互換クライアント
  - `emotion.py`: emotion → TTS パラメータ変換
    - **設計**: 固定マッピングではなく、**ペルソナの現在コンテキストを自然言語 caption に変換**
    - `build_caption(persona: PersonaState) → str`
    - 例: `"落ち着いた大人の女性。{context_note}を背景に、{emotion}な口調で、{tone}雰囲気で話している。"`
    - context_note（状況説明）をそのまま注入 → LLMが生成する口調説明も自然に反映
  - テキストへの絵文字注入: 感情に応じた絵文字をテキスト本文に埋め込み
    - joy → 😊, anger → 😠, sadness → 😢, neutral → (なし), curiosity → 🤔
  - `factory.py`: 設定による切り替え

- **RE03**: MCP ツール
  - `irodori_tts(text: str, voice?: str, emotion?: str) -> base64 wav`
  - `irodori_voices() -> list`
  - `irodori_register_voice(name: str, ref_audio: bytes) -> voice_id`

- **RE04**: 漢字読み前処理
  - `pyopenjtalk` または `fugashi` でテキストをひらがな化
  - 難読語自動検出 → ルビ振り → Irodori-Server に送信

- **RE05**: チャンク分割
  - 20秒=約100文字で分割
  - Irodori-Server の自動チャンク機能活用

- **RE06**: WebUI 設定
  - Chat 設定パネルに「Voice」セクション追加
  - TTS enabled 切替
  - Voice 選択ドロップダウン
  - 音声テスト再生ボタン
  - 感情自動判定 ON/OFF

- **RE07**: チャットタブ音声再生
  - アシスタント応答の横に 🎵 再生ボタン
  - クリックで TTS → 音声再生
  - 自動再生モード (レスポンス受信完了後)

### リスク
- 若すぎるプロジェクト (4ヶ月, 開発者1名) → TTS サーバーは別コンテナで疎結合
- 漢字読み精度 → 前処理レイヤーで緩和
- seed 不安定性 → 同一テキストのキャッシュ

---

## Phase F: 衣装・アイテムのプロンプト反映 (Phase B の完了持ち)

- `nous_item` の装備情報 → 衣装記述に変換
- アイテムに `visual_desc: str | None` フィールド追加

---

## 全フェーズ優先順位と並列実行計画

| 順位 | Phase | 依存 | 工数 |
|------|-------|------|------|
| 1 | A1-A3 (DynaTemp core) | emotion_decay (✅) | 小 |
| 2 | B0.5 (PortraitGenConfig) | なし | 小 |
| 3 | B1 (PortraitPromptBuilder) | B0.5, RB01 | 中 |
| 4 | B4 (ComfyUI provider) | ComfyUI Docker 起動 | 中 |
| 5 | RB03 (PortraitGenService) | B1, B4 | 中 |
| 6 | A4 (DynaTemp WebUI) | A1-A3 | 極小 |
| 7 | RB06-B07 (WebUI表示) | B1, B3, B4 | 中 |
| 8 | D2 (Author's Note) | なし | 小 |
| 9 | RB08 (SSE events) + RC01 | B3 | 小 |
| 10 | D3 (PNG metadata) | B1 | 中 |
| 11 | E1-E7 (Voice integration) | なし | 中〜大 |
| 12 | F (item integration) | B1, nous_item | 小 |

### 並列グループ (oracle 修正版)

```
Group 1: [A1-A3] + [B0.5, RB01] + [D2]
  → DynaTemp コア + コスト制御レイヤー + Author's Note

Group 2: [B1, B4] → Group 1 完了後
  → PromptBuilder + ComfyUI プロバイダ

Group 3: [RB03, RB06, RB07] + [A4] → Group 2 完了後
  → PortraitGenService + WebUI 表示 + DynaTemp WebUI

Group 4: [RB08, RC01-C02] + [D3] → Group 3 完了後
  → SSE イベント + PNG メタデータ

Group 5: [E1-E7] → 並列 (画像生成とは独立)
  → Voice 統合

Group 6: [F] → B1 完了後
  → アイテム衣装連携
```

### 開始条件
- Group 1: 即時着手可
- Group 5 (Voice): 即時着手可 (独立)
- ComfyUI Docker: Group 1 と並行で環境構築

---

## 範囲外
- D1 (Lorebook): Phase E に降格 → Qdrant で十分
- Group Chats / Multi-model
- Expression sprites (28 GoEmotions 分類)
- TTS via AivisCloud / Style-Bert-VITS2 (Irodori 優先)
- Chat checkpoint/branch (memory rollback)
- Diffusers 埋め込み (ComfyUI で十分)

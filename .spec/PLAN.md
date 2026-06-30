# PLAN — パパの口頭指示メモ (2026-06-30 → 2026-07-01 追加)

## 経緯
nous_ツールを一通り操作してレビューした。競合調査もした。忖度なしレビューを出したら、パパから対策指示が来た。

## パパの指示 (2026-06-30)
1. リランカー: `hotchpotch/japanese-reranker-xsmall-v2` 入れてるつもりだったのに機能してない → 調査して直す
2. エラーメッセージ: 英語に統一
3. 外部ストレージ対応: Postgres/Supabaseの基盤だけ作っておく
4. 他: ヘルタのレビュー提案通りに進めてOK（read_pdfバグ修正、スキルプリインストール、autoCapture、ドキュメント、goal_manageカテゴリ化）
5. **最重要**: 時間経過認識（昨日ぶりの会話）と感情推移（昨日怒ってたけど収まってきた）の改善点があればプランに入れる

→ **Phase 0-3 全タスク完了** (T01-T14, 1293+ tests, ruff 0 errors)

## パパの指示 (2026-07-01)
6. Dynamic Temperature — 感情で推論温度を動的に変える
7. **ペルソナのAI画像生成** — 固定画像じゃなくて、コンテキストに応じた動的生成。ローカルでやりたい（APIコストNG）
8. SillyTavern の良機能を Nous に採用（persona card、Author's Note 等）
9. 音声は後日 (Irodori-TTS 調査済み)

## 調査結果 (2026-07-01)
- ComfyUI: ローカル画像生成の決定版。Docker完備、アニメモデル対応 (Animagine XL 4.0)
- Irodori-TTS: MIT、日本語特化、OpenAI互換API。若いプロジェクト (4ヶ月) だが品質最良
- Dynamic Temperature: emotion_decay と組み合わせる独自実装
- Oracle レビュー: コスト制御が決定的に不足 → B0.5 (PortraitGenerationConfig, デフォルトOFF) 新設

## 優先順位
1. Dynamic Temp (Phase A) — 即時価値あり、小工数
2. ペルソナ動的画像 (Phase B) — パパの核心要望。ComfyUI 使う。**デフォルトOFFが鉄則**
3. 音声 (Phase E) — 独立 Phase。Irodori-TTS。後日着手推奨
4. Author's Note / Persona Card (Phase D) — 小工数から選別

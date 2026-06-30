# PLAN — パパの口頭指示メモ (2026-06-30)

## 経緯
nous_ツールを一通り操作してレビューした。競合調査もした。忖度なしレビューを出したら、パパから対策指示が来た。

## パパの指示
1. リランカー: `hotchpotch/japanese-reranker-xsmall-v2` 入れてるつもりだったのに機能してない → 調査して直す
2. エラーメッセージ: 英語に統一
3. 外部ストレージ対応: Postgres/Supabaseの基盤だけ作っておく
4. 他: ヘルタのレビュー提案通りに進めてOK（read_pdfバグ修正、スキルプリインストール、autoCapture、ドキュメント、goal_manageカテゴリ化）
5. **最重要**: 時間経過認識（昨日ぶりの会話）と感情推移（昨日怒ってたけど収まってきた）の改善点があればプランに入れる

## 調査結果サマリ
- リランカー: RerankerModelクラスは完全実装済みだが、一度もインスタンス化・呼び出しされてない。設定には `hotchpotch/japanese-reranker-xsmall-v2` と書いてある。
- 時間経過認識: FSRS v6 power-law曲線、9-factor composite strength score、感情トレンド表示はある。結構しっかりしてるが改善余地あり（body_state履歴なし、感情半減期固定値、emotion_historyのコンテキストトリガー未活用）
- エラーメッセージ: 日本語と英語が混在（"ファイルが見つかりません" vs "ok": true）

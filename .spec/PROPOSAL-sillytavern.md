# PROPOSAL — SillyTavern機能採用 + Dynamic Temperature + ペルソナ可視化 (2026-07-01)

## 調査サマリ

### SillyTavern 調査 (@librarian)
- **ライセンス**: AGPL-3.0 → 設計思想のみ採用、コード移植不可
- **Dynamic Temperature**: トークン分布ベース。感情ベース動的調整は**未実装**。Nousのemotion_decayと組み合わせる独自実装が鍵
- **Persona System**: Character Card V2/V3 PNGメタデータ埋め込み、28 GoEmotionsラベルの感情スプライト
- **Lorebook/World Info**: keyword-trigger記憶注入 — **Nous永続記憶強化に最適**
- **Author's Note**: 常時コンテキスト注入
- **Chat Vectorization**: 関連過去ログ検索注入
- **Memory Books/Summarize**: シーン分割 + 階層的要約

### Nous コードベース調査 (@explorer)
- **Temperature**: ✅ 完全実装 (0.0-2.0, default 0.7, Anthropic/OpenAI両対応)
- **top_p/top_k**: ❌ 未実装
- **画像生成**: ✅ DALL-E 2/3 + SD WebUI、MCPツールあり。生成画像はbase64のみ（ファイル保存なし）
- **WebUI**: ✅ SPA 11タブ、Tailwind CSS、REST+SSE。ペルソナ可視化は感情アイコン+身体バーのみ
- **ペルソナ画像/アバター**: ❌ 完全未実装
- **nous_item**: MCPツール名としては存在せず、REST APIのみ

---

## 採用ロードマップ

### Phase A: Dynamic Temperature — 情緒の揺らぎ [最優先]
**現状**: temperature 0.7固定
**目標**: 感情強度・種類に応じてtemperatureを動的変動

- **A1**: `nous/domain/sampling.py` 新設
  - `EmotionDrivenSampler` クラス
  - emotion + intensity → temperature, top_p 動的計算
  - DynaTemp風: `effective_temp = base_temp + emotion_modifier`
  - 感情別モディファイア: anger=+0.15, sadness=-0.1, joy=+0.05, excitement=+0.2 等
  - `top_p` も併せて動的調整（感情強度が高い時はtop_p下げてcoherent）

- **A2**: `ChatConfig` 拡張
  - `dynamic_temperature: bool = True`
  - `emotion_temperature_scale: float = 0.2`（感情の影響度）

- **A3**: `InferenceStep` 修正
  - `nous/application/chat/pipeline/inference.py` で EmotionDrivenSampler 適用

- **A4**: WebUI設定追加
  - チャット設定パネルにDynamic Temperature切替 + スケールスライダー

### Phase B: ペルソナ動的画像生成・表示 [最重要 - パパの核心要望]
**現状**: アバター/ポートレート完全なし
**方針**: 型にはめた固定画像ではなく、**コンテキスト＋チャット内容から自然言語プロンプトを生成し、AI画像生成で動的にペルソナの姿を描画**
→ 「ヘルタがうれしそうにアイス食べてる」のような状況表現が可能に

- **B1**: ペルソナPromptBuilder
  - `nous/domain/persona/portrait_prompt.py` 新設
  - 以下の情報から自然言語プロンプトを構築:
    - ペルソナ基本情報（外見description: 髪色、瞳、服装等）
    - 現在の感情・強度（`emotion` + `intensity`）
    - 身体状態（`fatigue`, `warmth`, `arousal`）
    - 現在の状況（`context_note`, `environment`）
    - 装備中のアイテム（`equipment` → 衣装記述）
    - 直近の会話トピック（`recent[0].content` 要約）
  - テンプレート例:
    ```
    {persona_description}, {emotion_adjective} expression, {body_state_desc},
    wearing {equipment_desc}, in {environment}, {activity_context},
    anime art style, high quality, {style_tags}
    ```

- **B2**: 画像生成キャッシュ機構
  - プロンプトのhash → 生成画像の短期キャッシュ（重複APIコール防止）
  - キャッシュTTL: 感情変化時は即時再生成、同一状態なら5分保持
  - 生成中はローディング表示（スケルトン＋パルスアニメーション）

- **B3**: ダッシュボードタブ — コンテキスト投影
  - Overviewタブ: 動的生成したペルソナ画像を表示
  - 感情/身体状態に応じてプロンプトが変化 → 生成画像も変化
  - 例: joy+excited → 笑顔で目を輝かせた姿 / sadness+tired → うつむき気味の姿

- **B4**: チャットタブ — 会話中の姿
  - チャット画面の人物表示エリア（左/右/上、設定切替可）
  - チャット内容に応じてプロンプトに活動コンテキストを追加
  - 例: 「アイスクリームの話」→ 「happily eating ice cream」がプロンプトに
  - 画像がない場合 or 生成中のフォールバック: 既存の感情アイコン

- **B5**: 衣装・アイテムのプロンプト反映
  - `nous_item` の装備情報をプロンプトの服装記述に変換
  - `equipment_desc` = "wearing {equipped_top}, {equipped_outer}, {equipped_accessories}"
  - アイテムに `visual_desc` フィールド追加（画像生成用の見た目記述）

### Phase C: WebUIペルソナ投影のリアルタイム化
**目標**: SSEで感情/身体状態の変化をリアルタイム反映

- **C1**: SSEイベント拡張
  - `events.py` に `emotion_change`, `body_state_change` イベント追加
  - ペルソナ画像表示をSSEで更新

- **C2**: 表情アニメーション
  - CSS transitionで表情切り替えをスムーズに
  - 感情強度に応じたアニメーション速度

### Phase D: SillyTavern機能採用（選択的）
**採用するもの**:
- **D1**: Lorebook風 keyword-trigger記憶注入
  - `persona_keyword_map` テーブル新設
  - キーワード出現 → 関連記憶を自動注入
  - Qdrantベクトル検索と併用

- **D2**: Author's Note風 常時注入
  - `persona.author_note` フィールド追加
  - 全メッセージに自動注入（frequency制御可）

- **D3**: ペルソナPNGメタデータ埋め込み
  - PNG tEXtチャンクにペルソナデータ（name, description, avatar, emotion tags）を埋め込み
  - import/export形式として採用
  - Character Card V2/V3互換でSillyTavernユーザーとの相互運用

**採用しないもの**:
- SillyTavern Extras連携（deprecated）
- Group Chats（Nousは1対1設計）
- TTS/Translation（本筋外）
- Chat Vectorization（Qdrantで既に実装済み）
- Quick Reply event hooks（L2 EventBusでカバー）

---

## 実装優先順位

| 順位 | Phase | 内容 | 工数見積 | 依存 |
|------|-------|------|----------|------|
| 1 | A1-A3 | Dynamic Temperature コア実装 | 小 | emotion_decay（✅済） |
| 2 | B1 | PromptBuilder（自然言語→画像プロンプト） | 小 | なし |
| 3 | B2 | 画像生成キャッシュ機構 | 小 | B1, image_gen（✅済） |
| 4 | B3 | ダッシュボード投影 | 中 | B1, B2 |
| 5 | B4 | チャット動的画像表示 | 中 | B1, B2 |
| 6 | A4 | Dynamic Temp WebUI設定 | 極小 | A1-A3 |
| 7 | C1-C2 | リアルタイムSSE反映 | 小 | B3, B4 |
| 8 | B5 | 衣装プロンプト反映（nous_item拡張） | 小 | B1, nous_item |
| 9 | D3 | PNGメタデータ埋め込み | 中 | B1 |
| 10 | D1 | Lorebook風キーワード記憶 | 大 | なし |
| 11 | D2 | Author's Note常時注入 | 小 | なし |

## 並列実行可能グループ
```
Group 1（即時並列）: [A1-A3] + [B1] + [D1準備]
Group 2（Group 1後）: [B2] + [B5] + [A4] + [D2]
Group 3（Group 2後）: [B3] + [B4]
Group 4（最終）: [C1-C2] + [D3] + [D1本実装]
```

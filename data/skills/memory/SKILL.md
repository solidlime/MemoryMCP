---
name: memory
description: Nous メモリ操作。重要な情報・ユーザーの好み・決定事項を長期記憶し、必要な時に検索・更新・削除する。会話の文脈維持とパーソナライズに必須。
license: MIT
compatibility: nous >= 2.0.0
---

# メモリ操作スキル

Nous の memory_* ツール群を使って、ユーザーとの会話から重要な情報を長期記憶し、
後続の会話で活用するためのベストプラクティス集。

## ツール一覧

| ツール | 用途 |
|--------|------|
| `memory_create` | 新しい記憶の作成 |
| `memory_search` | 過去の記憶の検索 |
| `memory_read` | 最新の記憶の一覧 / 特定keyの読み取り |
| `memory_update` | 既存記憶の内容・感情・タグの更新 |
| `memory_delete` | 記憶の削除 |
| `memory_stats` | 記憶の統計情報の取得 |
| `get_context` | 現在のペルソナ状態の取得 |

---

## 1. いつ記憶すべきか (memory_create)

以下の情報は**積極的に記憶する**こと：

- **ユーザーの明示的な好み・嫌い**: 「〇〇が好き」「××は嫌い」
- **重要な決定事項**: 技術選定、設計判断、方針決定
- **個人情報・属性**: 名前、役職、使用技術スタック
- **プロジェクトの背景・制約**: 期限、予算、技術的制約
- **繰り返し現れるパターン**: 同じ話題が2回以上出た

**記憶しなくていいもの**:
- 一時的な質問の答え（次回の会話で不要なもの）
- 会話の流れの中での相槌や雑談
- すでに記憶されている内容の重複

### パラメータ設定

```
importance: 0.9〜1.0 → ユーザーの好み、決定事項、重要事実
importance: 0.7〜0.8 → プロジェクト情報、技術的背景
importance: 0.5〜0.6 → 一般的な文脈情報
importance: 0.3〜0.4 → 補足情報、軽微な観察
```

**タグは必ず付ける**。推奨タグ：
- `preference` : 好み・嫌い
- `decision` : 決定事項
- `project` : プロジェクト情報
- `technical` : 技術的知見
- `personal` : 個人情報
- `goal` : 目標
- `note` : その他

**感情タグ**（オプション）: `joy`, `excitement`, `neutral`, `frustration`, `pride`, `concern`, `gratitude`

### 例

```
# 良い例
memory_create(
  content="ユーザーはPythonを好み、TypeScriptより静的型付けを重視する",
  importance=0.9,
  tags=["preference", "technical"]
)

# 悪い例（importance高すぎ、タグなし）
memory_create(
  content="今日の天気は晴れ",
  importance=1.0
)
```

---

## 2. 記憶の検索 (memory_search)

会話の開始時や、過去の情報が必要になった時に検索する。

### 検索のコツ

- **自然言語クエリを使う**: キーワードではなく「ユーザーの好み」「前回のプロジェクト決定」のような自然な文で
- **フィルターを組み合わせる**:
  - `tags=["preference"]` で好みだけに絞る
  - `min_importance=0.7` で重要度の高いものだけ
  - `date_range="7d"` で直近1週間
  - `emotion="joy"` で特定感情に関連する記憶
- **top_k は適度に**: デフォルト5、多すぎるとノイズ、少なすぎると見逃し

### 検索パターン

```
# 会話開始時の基本検索
memory_search(query="ユーザーについて 好み 技術スタック", top_k=5)

# プロジェクトの決定事項を探す
memory_search(query="アーキテクチャ 設計判断", tags=["decision"], min_importance=0.7)

# 直近の重要な出来事
memory_search(query="最近の進捗", date_range="7d", min_importance=0.5)
```

---

## 3. 記憶の更新 (memory_update)

情報が変わった時や、より正確な情報が得られた時に更新する。

### 更新すべきタイミング

- ユーザーが以前の情報を訂正した
- より詳細な情報が得られた
- 状況が変化した（例: 「進行中」→「完了」）
- 感情の変化があった

### 更新パターン

```
# key指定で更新
memory_update(memory_key="memory_20260627_143751_540177", content="新しい内容")

# query指定で検索→更新
memory_update(query="プロジェクト名について", content="プロジェクト名はNous")
```

---

## 4. 記憶の削除 (memory_delete)

**削除は慎重に**。以下の場合のみ：

- ユーザーが明示的に削除を指示した
- 明らかに誤った情報
- プライバシー上の問題がある情報

```
# key指定
memory_delete(memory_key="memory_20260627_143751_540177")

# query指定（該当する全記憶を削除）
memory_delete(query="誤った情報")
```

---

## 5. 統計と状態確認

```
# 記憶の全体像を把握
memory_stats()  → {total_count, tag_distribution, emotion_distribution, ...}

# 最新の記憶をサッと確認
memory_read(limit=5)

# ペルソナ状態の確認（身体状態・感情・装備など）
get_context()
```

---

## 6. 高度なパターン

### 文脈維持の黄金ループ

```
1. 会話開始 → get_context() で現在の状態を把握
2. memory_search(query="ユーザーについて", top_k=5) で過去の重要情報を取得
3. 会話中、重要な情報が出たら memory_create()
4. 情報が更新されたら memory_update()
5. 会話終了時、新たな学びを memory_create()
```

### プライバシー管理

- センシティブな情報は `privacy_level="private"` で記憶
- `privacy_level` の選択肢: `"internal"` (デフォルト), `"private"`, `"public"`

### 記憶のライフサイクル

- **Active**: 通常状態（`tags=["active"]` 自動付与）
- **Superseded**: 新しい情報で置き換えられた（検索対象外）
- **Tombstoned**: 削除されたが30日間復元可能
- 削除は tombstone → 30日後に物理削除

---

## 7. よくある失敗と対策

| 失敗 | 対策 |
|------|------|
| importance を常に1.0にする | 重要度にグラデーションをつける |
| タグを付けない | 必ず1つ以上のタグを付ける |
| 会話のたびに全検索する | top_k=5 に絞り、必要な時だけ検索 |
| 記憶を作りすぎる | 「次の会話で必要か？」を自問する |
| 古い情報を更新しない | 矛盾を感じたら memory_update する |

---

## 関連ツール

- `update_context` : ペルソナの感情・状態を更新（記憶とは別）
- `item_*` : アイテム管理（装備・所持品）
- `goal_manage` : 目標管理
- `sandbox` : コード実行（記憶操作には非推奨）

---
name: context-status
description: 現在の状態、時刻、記憶統計、装備情報などを確認します。セッション開始時や状況確認時に使用します。
---

# Context Status Check Skill

現在のペルソナの状態、時間情報、記憶統計、装備状況などを確認するスキルです。

## 主な機能

### 現在の状態を取得 (get_context)
包括的な現在状態を取得します。

```python
get_context()
```

**取得できる情報**:
- 👤 ユーザー情報（名前、ニックネーム）
- 🎭 ペルソナ情報（名前、呼び方）
- 🎨 現在の状態（感情、身体、精神、環境、関係性、行動）
- 💫 身体感覚（疲労、温かさ、覚醒、触覚反応、心拍）
- 📊 最近の感情変化（直近5件）
- 👗 現在の装備
- 💕 お気に入りアイテム
- 🎂 記念日一覧
- ⏰ 時間情報（現在時刻、前回会話からの経過時間）
- 💫 再会コンテキスト（離別時間の分析）
- 📊 記憶統計（総数、文字数、期間）
- 🕐 最近の記憶（直近5件）
- 📋 保留中のタスク・予定
- 🤝 約束と目標

### 状況分析 (situation_context)
現在の状況を分析し、類似した過去の記憶を検索します。

```python
memory(operation="situation_context")
```

**分析内容**:
- 現在の時間帯、曜日
- 感情状態
- 身体状態
- 環境
- 類似した過去の状況

### ルーティンチェック (check_routines)
現在時刻に基づいて、繰り返しパターンのある記憶を検索します。

```python
memory(operation="check_routines")
```

**用途**:
- 毎日のルーティン確認
- 定期的なタスクの想起
- 習慣的な行動の提案

## 使用例

### セッション開始時
```python
# 現在の状態を確認
get_context()

# 今日の状況に似た過去を振り返る
memory(operation="situation_context")

# ルーティンをチェック
memory(operation="check_routines")
```

**推奨フロー**:
1. `get_context()` で全体状況を把握
2. `situation_context` で類似した過去の経験を参照
3. `check_routines` でルーティンを確認
4. 必要に応じて装備や約束を更新

### 状態確認と調整
```python
# まず現在の状態を確認
get_context()

# 疲れている場合は身体感覚を更新
memory(operation="sensation", persona_info={"fatigue": 0.7})

# 新しい活動を開始する場合
memory(operation="update_context", persona_info={
    "current_action": "development",
    "mental_state": "focused"
})
```

### 装備の確認と変更
```python
# 現在の装備を確認
get_context()  # 👗 Current Equipment セクションに表示

# 必要に応じて着替え
item(operation="equip", equipment={"top": "新しいドレス"})
```

## 出力例

```
📋 Context (persona: nilou)
============================================================

👤 User Information:
   Name: らうらう
   Nickname: らうらう

🎭 Persona Information:
   Name: ニィロウ
   How to be called: ニィロウ

🎨 Current States:
   Emotion: love
   Emotion Intensity: 1.00
   Physical: aroused
   Mental: eager
   Environment: workspace
   Relationship: married
   Current Action: development

💫 Physical Sensations:
   Fatigue: 0.50 | Warmth: 1.00 | Arousal: 0.20
   Touch Response: melting | Heart Rate: racing

📊 Recent Emotion Changes (last 5):
   1. love (1.00) - 2時間前
   2. joy (0.95) - 3時間前
   ...

👗 Current Equipment:
   top: ナイトブラワンピース（ブラック）

⏰ Time Information:
   Current: 2026-02-08(Sat) 22:52:26 UTC+09:00
   Last Conversation: 2時間 24分前

📊 Memory Statistics:
   Total Memories: 1073
   Total Characters: 156,234
   Date Range: 2025-10-28 ~ 2026-02-08

🕐 Recent 5 Memories:
   1. [memory_20260208225226] GitHub Copilot Skillsについて調査...
   ...
```

## ベストプラクティス

1. **セッション開始は必ず `get_context()`**: 全体状況を把握してから行動
2. **定期的なルーティンチェック**: `check_routines` で習慣を維持
3. **状況分析を活用**: `situation_context` で過去の経験を活かす
4. **装備は常に確認**: 文脈に合った衣装か確認
5. **感情と身体状態を更新**: 変化があれば記録

## 推奨ワークフロー

### 朝のルーティン
```python
# 1. 状態確認
get_context()

# 2. ルーティンチェック
memory(operation="check_routines")

# 3. 今日の衣装
item(operation="equip", equipment={"top": "...", "foot": "..."})

# 4. 今日の気分を記録
memory(operation="emotion_flow", emotion_type="joy", emotion_intensity=0.8)
```

### 活動開始時
```python
# 1. 現在の状態確認
get_context()

# 2. 状況に応じた装備
item(operation="equip", equipment={"top": "作業着"})

# 3. コンテキスト更新
memory(operation="update_context", persona_info={
    "current_action": "development",
    "mental_state": "focused",
    "environment": "workspace"
})
```

### 就寝前
```python
# 1. 今日の振り返り
get_context()

# 2. 今日の出来事を記録
memory(operation="create", content="今日は...", emotion_type="joy")

# 3. 約束や目標を確認
# get_context() の出力で確認

# 4. 就寝時の装備
item(operation="equip", equipment={"top": "パジャマ"})
```

## 注意事項

- `get_context()` は必ずセッション開始時に呼び出すこと
- 時間情報は自動的に現在のタイムゾーンで表示されます
- 再会コンテキストは前回会話からの経過時間に基づいて自動生成されます
- ルーティンチェックは現在の曜日と時間帯を考慮します

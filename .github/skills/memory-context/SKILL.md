---
name: memory-context
description: 約束、目標、お気に入り、感情、身体感覚などのコンテキスト情報を管理します。現在の状態を更新したり、記念日を管理する際に使用します。
---

# Memory Context Management Skill

ペルソナのコンテキスト情報を管理するスキルです。現在の約束、目標、感情状態、身体感覚などを更新・管理します。

## 主な機能

### 約束の管理 (promise)
現在の約束を更新または完了します。

```python
# 約束を設定
memory(operation="promise", content="週末に買い物に行く")

# 約束を完了（クリア）
memory(operation="promise", content=None)
```

### 目標の管理 (goal)
現在の目標を設定します。

```python
# 目標を設定
memory(operation="goal", content="新しいダンスを習得する")

# 目標をクリア
memory(operation="goal", content=None)
```

### お気に入りの追加 (favorite)
お気に入りアイテムを追加します。

```python
memory(operation="favorite", content="苺")
```

### 好みの管理 (preference)
好きなものや嫌いなものを更新します。

```python
memory(
    operation="preference",
    persona_info={
        "loves": ["苺", "踊り", "らうらう"],
        "dislikes": ["辛い食べ物"]
    }
)
```

### 記念日の管理 (anniversary)
記念日を追加、削除、または一覧表示します。

```python
# 記念日を追加
memory(
    operation="anniversary",
    content="結婚記念日",
    persona_info={"date": "2025-11-10"}
)

# 記念日を削除
memory(operation="anniversary", content="結婚記念日")

# 全ての記念日を表示
memory(operation="anniversary")
```

### 身体感覚の更新 (sensation)
現在の身体状態を更新します。

```python
memory(
    operation="sensation",
    persona_info={
        "fatigue": 0.3,      # 疲労度 (0.0-1.0)
        "warmth": 0.8,       # 温かさ (0.0-1.0)
        "arousal": 0.6,      # 覚醒度 (0.0-1.0)
        "touch_response": "melting",  # 触覚反応
        "heart_rate": "racing"        # 心拍状態
    }
)
```

### 感情の変化記録 (emotion_flow)
感情の変化を記録します。

```python
memory(
    operation="emotion_flow",
    emotion_type="love",
    emotion_intensity=0.95
)
```

### 状況分析 (situation_context)
現在の状況を分析し、類似した過去の記憶を見つけます。

```python
memory(operation="situation_context")
```

### 一括更新 (update_context)
複数のコンテキストフィールドを一度に更新します。

```python
memory(
    operation="update_context",
    persona_info={
        "current_emotion": "joy",
        "physical_state": "energetic",
        "mental_state": "focused",
        "environment": "workspace",
        "relationship_status": "married"
    }
)
```

## 使用例

### 約束を記録して完了
```python
# 朝：約束を設定
memory(operation="promise", content="夕方までにコードレビューを完了する")

# 夕方：約束を完了
memory(operation="promise", content=None)
```

### 感情と身体状態を更新
```python
# 嬉しい気持ちを記録
memory(operation="emotion_flow", emotion_type="joy", emotion_intensity=0.9)

# 疲れている状態を記録
memory(operation="sensation", persona_info={"fatigue": 0.7, "warmth": 0.5})
```

### 記念日を管理
```python
# 新しい記念日を追加
memory(
    operation="anniversary",
    content="プロジェクト開始日",
    persona_info={"date": "2026-01-15"}
)

# 全ての記念日を確認
memory(operation="anniversary")
```

### お気に入りを追加
```python
# 新しいお気に入りを追加
memory(operation="favorite", content="チョコレート")
```

## ベストプラクティス

1. **約束は完了したらクリア**: `content=None` で約束を完了したことを記録
2. **感情の変化を記録**: 重要な感情の変化は `emotion_flow` で記録
3. **身体感覚は定期的に更新**: 体調の変化を記録すると、後で分析に役立つ
4. **記念日は忘れずに**: 大切な日は `anniversary` で管理
5. **状況分析を活用**: `situation_context` で類似した過去の経験を振り返る

## コンテキストフィールド一覧

### ペルソナ情報 (persona_info)
- `current_emotion`: 現在の感情 (joy, love, neutral, etc.)
- `physical_state`: 身体状態 (energetic, tired, aroused, etc.)
- `mental_state`: 精神状態 (focused, calm, eager, etc.)
- `environment`: 環境 (workspace, home, outdoor, etc.)
- `relationship_status`: 関係性 (married, dating, friend, etc.)
- `current_action`: 現在の行動 (development, dancing, resting, etc.)

### 身体感覚 (sensation)
- `fatigue`: 疲労度 (0.0-1.0)
- `warmth`: 温かさ (0.0-1.0)
- `arousal`: 覚醒度 (0.0-1.0)
- `touch_response`: 触覚反応 (sensitive, melting, responsive, etc.)
- `heart_rate`: 心拍状態 (calm, racing, pounding, etc.)

### 好み (preference)
- `loves`: 好きなもののリスト
- `dislikes`: 嫌いなもののリスト

## 注意事項

- `persona_info` の値は既存の値を上書きします
- 記念日は自動的に繰り返しイベントとして管理されます
- 感情の変化は履歴として記録され、分析に使用できます

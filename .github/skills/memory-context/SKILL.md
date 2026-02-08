---
name: memory-context
description: 約束、目標、お気に入り、感情、身体感覚などのコンテキスト情報を管理します。現在の状態を更新したり、記念日を管理する際に使用します。
---

# Memory Context Management Skill

ペルソナのコンテキスト情報を管理するスキルです。約束、目標、感情状態、身体感覚などを更新・管理します。

## API仕様

**エンドポイント**: `POST {memory_mcp_url}/api/tools/memory`
**ヘッダー**: `Authorization: Bearer {memory_persona}`

### 約束の管理 (promise)

```bash
# 約束を設定
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "promise", "content": "週末に買い物に行く"}'

# 約束を完了（クリア）
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "promise", "content": null}'
```

### 目標の管理 (goal)

```bash
# 目標を設定
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "goal", "content": "新しいダンスを習得する"}'

# 目標をクリア
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "goal", "content": null}'
```

### お気に入りの追加 (favorite)

```bash
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "favorite", "content": "苺"}'
```

### 好みの管理 (preference)

```bash
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "preference",
    "persona_info": {
      "loves": ["苺", "踊り", "らうらう"],
      "dislikes": ["辛い食べ物"]
    }
  }'
```

### 記念日の管理 (anniversary)

```bash
# 記念日を追加
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "anniversary",
    "content": "結婚記念日",
    "persona_info": {"date": "2025-11-10"}
  }'

# 記念日一覧
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type": application/json" \
  -d '{"operation": "anniversary"}'

# 記念日を削除
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "anniversary", "content": "結婚記念日"}'
```

### 身体感覚の更新 (sensation)

```bash
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "sensation",
    "persona_info": {
      "fatigue": 0.3,
      "warmth": 0.8,
      "arousal": 0.6
    }
  }'
```

**パラメータ**: 0.0-1.0の範囲
- `fatigue`: 疲労度
- `warmth`: 温かさ
- `arousal`: 覚醒度

### 感情の変化を記録 (emotion_flow)

```bash
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "emotion_flow",
    "emotion_type": "love",
    "emotion_intensity": 0.95
  }'
```

### 現在の状況を分析 (situation_context)
現在の状況（時間帯、装備、最近の記憶）を分析し、類似する過去の記憶を探します。

```bash
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "situation_context"}'
```

### 複数のコンテキスト更新 (update_context)

```bash
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "update_context",
    "persona_info": {
      "active_promise": "明日までにコードレビュー",
      "current_goal": "新機能リリース",
      "favorites": ["苺", "踊り"]
    }
  }'
```

## 使用例

### セッション開始時のワークフロー

```bash
# 1. 状況分析
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "situation_context"}'

# 2. ルーティンチェック
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "check_routines"}'
```

### 感情と身体状態の更新

```bash
# 嬉しい出来事があったとき
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "emotion_flow", "emotion_type": "joy", "emotion_intensity": 0.9}'

# 疲れているとき
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "sensation", "persona_info": {"fatigue": 0.7, "warmth": 0.5}}'
```

## ベストプラクティス

1. **定期的な更新**: セッション開始時に `situation_context` で状態確認
2. **約束の管理**: 完了したら必ず `content: null` でクリア
3. **感情記録**: 重要な感情変化は `emotion_flow` で記録
4. **身体状態**: 体調変化を `sensation` で追跡
5. **記念日**: 重要な日付は `anniversary` で管理

## 注意事項

- `situation_context` は現在の装備、記憶、時間帯を考慮して分析します
- 感情と身体感覚は別々に記録されます
- 記念日は月日のみで管理され、年は無視されます

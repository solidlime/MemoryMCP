---
name: memory-context
description: 約束、目標、お気に入り、感情、身体感覚などのコンテキスト情報を管理します。現在の状態を更新したり、記念日を管理する際に使用します。
---

# Memory Context Management Skill

ペルソナのコンテキスト情報を管理します。約束、目標、感情状態、身体感覚などを更新・管理できます。

## 使い方

```bash
# 約束を設定
python .github/skills/scripts/memory_mcp.py memory promise '{"content": "週末に買い物に行く"}'

# 目標を設定
python .github/skills/scripts/memory_mcp.py memory goal '{"content": "新しいダンスを習得する"}'

# 身体感覚を更新
python .github/skills/scripts/memory_mcp.py memory sensation '{"persona_info": {"fatigue": 0.3, "warmth": 0.8}}'

# 感情を記録
python .github/skills/scripts/memory_mcp.py memory emotion_flow '{"emotion_type": "love", "emotion_intensity": 0.95}'

# 状況分析
python .github/skills/scripts/memory_mcp.py memory situation_context
```

## 主な操作

### promise - 約束の管理
```bash
# 約束を設定
python .github/skills/scripts/memory_mcp.py memory promise '{"content": "明日までにコードレビュー"}'

# 約束をクリア
python .github/skills/scripts/memory_mcp.py memory promise '{"content": null}'
```

### goal - 目標の管理
```bash
# 目標を設定
python .github/skills/scripts/memory_mcp.py memory goal '{"content": "新機能リリース"}'

# 目標をクリア
python .github/skills/scripts/memory_mcp.py memory goal '{"content": null}'
```

### favorite - お気に入りの追加
```bash
python .github/skills/scripts/memory_mcp.py memory favorite '{"content": "苺"}'
```

### preference - 好みの管理
```bash
python .github/skills/scripts/memory_mcp.py memory preference '{
  "persona_info": {
    "loves": ["苺", "踊り", "らうらう"],
    "dislikes": ["辛い食べ物"]
  }
}'
```

### anniversary - 記念日の管理
```bash
# 記念日を追加
python .github/skills/scripts/memory_mcp.py memory anniversary '{
  "content": "結婚記念日",
  "persona_info": {"date": "2025-11-10"}
}'

# 記念日一覧
python .github/skills/scripts/memory_mcp.py memory anniversary

# 記念日を削除
python .github/skills/scripts/memory_mcp.py memory anniversary '{"content": "結婚記念日"}'
```

### sensation - 身体感覚の更新
```bash
python .github/skills/scripts/memory_mcp.py memory sensation '{
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

### emotion_flow - 感情の変化を記録
```bash
python .github/skills/scripts/memory_mcp.py memory emotion_flow '{
  "emotion_type": "love",
  "emotion_intensity": 0.95
}'
```

### situation_context - 現在の状況を分析
現在の状況（時間帯、装備、最近の記憶）を分析し、類似する過去の記憶を探します。

```bash
python .github/skills/scripts/memory_mcp.py memory situation_context
```

### update_context - 複数のコンテキスト更新
```bash
python .github/skills/scripts/memory_mcp.py memory update_context '{
  "persona_info": {
    "active_promise": "明日までにコードレビュー",
    "current_goal": "新機能リリース",
    "favorites": ["苺", "踊り"]
  }
}'
```

## セッション開始ワークフロー

```bash
# 1. 状況分析
python .github/skills/scripts/memory_mcp.py memory situation_context

# 2. ルーティンチェック
python .github/skills/scripts/memory_mcp.py memory check_routines
```

## コツ

1. **状況分析を活用** - `situation_context` で現在の装備・時間・記憶を総合判断
2. **ルーティン検出** - `check_routines` で定期行動パターンを把握
3. **約束・目標の管理** - アクティブな約束や目標があれば優先対応
4. **身体感覚の反映** - 疲労度や温かさに応じて行動を調整
5. **感情の記録** - 重要な感情の変化は `emotion_flow` で記録

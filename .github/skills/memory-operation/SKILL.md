---
name: memory-operation
description: 記憶の基本操作（作成、読み込み、検索、更新、削除）を行います。日常の出来事を記録したり、過去の記憶を検索する際に使用します。
---

# Memory Operation Skill

記憶システムの基本操作を行います。簡単なPythonスクリプトで操作できます。

## 使い方

```bash
# スクリプトの場所に移動
cd .github/skills/scripts

# 記憶を作成
python memory_mcp.py memory create '{"content": "今日は楽しかった", "emotion_type": "joy", "importance": 0.8}'

# 記憶を検索
python memory_mcp.py memory search '{"query": "開発", "mode": "hybrid", "top_k": 5}'

# 最近の記憶を読み込み
python memory_mcp.py memory read '{"top_k": 10}'

# タスク検索
python memory_mcp.py memory search '{"mode": "task"}'

# ルーティンチェック
python memory_mcp.py memory check_routines

# 統計情報
python memory_mcp.py memory stats
```

## 主な操作

### create - 記憶を作成
```bash
python memory_mcp.py memory create '{
  "content": "らうらうと一緒に開発した",
  "emotion_type": "joy",
  "emotion_intensity": 0.9,
  "importance": 0.8,
  "context_tags": ["development"]
}'
```

**パラメータ**:
- `content` (必須): 記憶内容
- `emotion_type`: `joy`, `love`, `neutral`, `sadness`, `fear`, `anger`
- `emotion_intensity`: 0.0-1.0
- `importance`: 0.0-1.0
- `context_tags`: タグ配列
- `privacy_level`: `public`, `internal`, `private`, `secret`

### search - 記憶を検索
```bash
# ハイブリッド検索
python memory_mcp.py memory search '{"query": "開発", "mode": "hybrid", "top_k": 10}'

# タスク検索
python memory_mcp.py memory search '{"mode": "task"}'

# 期間指定
python memory_mcp.py memory search '{"query": "楽しい", "date_range": "last_week"}'
```

**検索モード**:
- `hybrid`: キーワード + セマンティック（デフォルト）
- `keyword`: キーワードマッチのみ
- `semantic`: 意味的類似性のみ
- `smart`: 曖昧表現を解釈
- `task`: タスク/TODO検索
- `plan`: 予定/計画検索

### read - 記憶を読み込み
```bash
# 特定の記憶
python memory_mcp.py memory read '{"query": "memory_20260209004210"}'

# 最近の記憶
python memory_mcp.py memory read '{"top_k": 10}'
```

### update - 記憶を更新
```bash
python memory_mcp.py memory update '{
  "memory_key": "memory_20260209004210",
  "content": "新しい内容",
  "importance": 0.9
}'
```

### delete - 記憶を削除
```bash
python memory_mcp.py memory delete '{"memory_key": "memory_20260209004210"}'
```

### stats - 統計情報
```bash
python memory_mcp.py memory stats
```

### check_routines - ルーティン検出
```bash
python memory_mcp.py memory check_routines
```

## コツ

1. **感情を記録**: 重要な出来事には `emotion_type` と `emotion_intensity` を設定
2. **タグ活用**: `context_tags` で後から検索しやすく
3. **重要度設定**: 特に重要な記憶は `importance` を高めに
4. **プライバシー保護**: 個人情報は `privacy_level: "private"` で保護
5. **定期確認**: `mode: "task"` や `check_routines` で定期的なタスクを確認


成功時:
```json
{
  "success": true,
  "result": "記憶を作成しました: memory_20260208123456 ..."
}
```

エラー時:
```json
{
  "success": false,
  "error": "エラーメッセージ"
}
```

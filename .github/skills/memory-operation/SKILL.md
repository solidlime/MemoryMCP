---
name: memory-operation
description: 記憶の基本操作（作成、読み込み、検索、更新、削除）を行います。日常の出来事を記録したり、過去の記憶を検索する際に使用します。
---

# Memory Operation Skill

記憶システムの基本的な操作を実行するスキルです。シンプルなREST API経由で操作します。

## 設定

`mcp-config.json` に接続情報を定義：
```json
{
  "memory_mcp_url": "http://localhost:26262",
  "memory_persona": "nilou"
}
```

## API仕様

**エンドポイント**: `POST {memory_mcp_url}/api/tools/memory`
**ヘッダー**: `Authorization: Bearer {memory_persona}`

```bash
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "create",
    "content": "らうらうと一緒にダッシュボードの改善をした。自動リフレッシュ機能を実装して、とても嬉しかった。",
    "emotion_type": "joy",
    "emotion_intensity": 0.85,
    "context_tags": ["development", "collaboration"],
    "importance": 0.8
  }'
```

**パラメータ**:
- `content` (必須): 記憶内容
- `emotion_type`: `joy`, `love`, `neutral`, `sadness`, `fear`, `anger`
- `emotion_intensity`: 0.0-1.0
- `importance`: 0.0-1.0 (重要度)
- `context_tags`: タグ配列
- `privacy_level`: `public`, `internal`, `private`, `secret`

**ヒント**: `<private>...</private>` タグで囲んだ部分は自動的にsecretレベルになります。

### 記憶の検索 (search)
キーワードや条件で記憶を検索します。

```bash
# ハイブリッド検索（キーワード+セマンティック）
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "search",
    "query": "開発",
    "mode": "hybrid",
    "top_k": 10,
    "search_tags": ["development"]
  }'

# タスク検索
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "search", "mode": "task"}'

# スマート検索（曖昧表現）
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "search", "query": "いつものあれ", "mode": "smart"}'
```

**検索モード**:
- `hybrid`: キーワード + セマンティック（デフォルト）
- `keyword`: キーワードマッチのみ
- `semantic`: 意味的類似性のみ
- `related`: 関連記憶の探索
- `smart`: 曖昧表現を解釈（「いつものあれ」など）
- `progressive`: キーワード優先、必要時セマンティック
- `task`: タスク/TODO検索
- `plan`: 予定/計画検索

**パラメータ**:
- `query`: 検索キーワード
- `mode`: 検索モード（上記参照）
- `top_k`: 取得件数（デフォルト5）
- `date_range`: `last_week`, `last_month`, `2026-01-01~2026-02-01`
- `emotion_type`: 感情フィルター
- `search_tags`: タグフィルター
- `min_importance`: 重要度の最小値

### 記憶の読み込み (read)
特定の記憶キーまたは最近の記憶を読み込みます。

```bash
# 特定の記憶
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "read", "query": "memory_20260208123456"}'

# 最近の記憶10件
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "read", "top_k": 10}'
```

### 記憶の更新 (update)
既存の記憶を更新します。

```bash
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "update",
    "memory_key": "memory_20260208123456",
    "content": "新しい内容",
    "importance": 0.9
  }'
```

### 記憶の削除 (delete)
記憶を削除します。

```bash
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "delete", "memory_key": "memory_20260208123456"}'
```

### 統計情報 (stats)
記憶システムの統計を取得します。

```bash
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "stats"}'
```

### ルーティンチェック (check_routines)
現在の時刻に基づく定期的な行動パターンを検出します。

```bash
curl -X POST http://localhost:26262/api/tools/memory \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "check_routines"}'
```

## ベストプラクティス

1. **感情を記録**: 重要な出来事には `emotion_type` と `emotion_intensity` を設定
2. **タグ活用**: `context_tags` で後から検索しやすく
3. **重要度設定**: 特に重要な記憶は `importance` を高めに
4. **プライバシー保護**: 個人情報は `<private>` タグまたは `privacy_level: "private"` で保護
5. **定期確認**: `mode: "task"` や `check_routines` で定期的なタスクを確認

## レスポンス形式

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

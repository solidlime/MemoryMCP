---
name: memory-operation
description: 記憶の基本操作（作成、読み込み、検索、更新、削除）を行います。日常の出来事を記録したり、過去の記憶を検索する際に使用します。
---

# Memory Operation Skill

記憶システムの基本的な操作を実行するスキルです。

## 主な機能

### 記憶の作成 (create)
新しい記憶を作成します。出来事、会話、学び、感情などを記録できます。

```python
memory(
    operation="create",
    content="<記憶したい内容>",
    emotion_type="joy|love|neutral|sadness",  # オプション
    emotion_intensity=0.0-1.0,  # オプション
    importance=0.0-1.0,  # オプション
    context_tags=["tag1", "tag2"],  # オプション
    privacy_level="public|internal|private|secret"  # オプション、デフォルトinternal
)
```

**重要**: `<private>...</private>` タグで囲んだ部分は自動的に秘密レベルになります。

### 記憶の読み込み (read)
特定の記憶キーまたは最近の記憶を読み込みます。

```python
# 特定の記憶を読み込む
memory(operation="read", query="memory_20260208123456")

# 最近の記憶を読み込む（デフォルト5件）
memory(operation="read", top_k=10)
```

### 記憶の検索 (search)
様々な条件で記憶を検索します。

```python
memory(
    operation="search",
    query="検索キーワード",
    mode="hybrid|keyword|semantic|related|smart|progressive|task|plan",
    top_k=5,  # 取得件数
    date_range="last_week|last_month|2026-01-01~2026-02-01",  # オプション
    emotion_type="joy",  # オプション
    search_tags=["tag1", "tag2"],  # オプション
    min_importance=0.5  # オプション
)
```

**検索モード**:
- `hybrid` (デフォルト): キーワード + セマンティック検索
- `keyword`: キーワードマッチのみ
- `semantic`: 意味的類似性のみ
- `related`: 関連記憶の検索
- `smart`: 「いつものあれ」など曖昧な表現に対応
- `progressive`: キーワード優先、必要に応じてセマンティック
- `task`: タスク/TODO検索
- `plan`: 予定/計画検索

### 記憶の更新 (update)
既存の記憶を更新します。

```python
memory(
    operation="update",
    memory_key="memory_20260208123456",
    content="<新しい内容>",  # オプション
    context_tags=["new_tag"],  # オプション
    importance=0.8  # オプション
)
```

### 記憶の削除 (delete)
記憶を削除します。

```python
memory(operation="delete", memory_key="memory_20260208123456")
```

### 統計情報 (stats)
記憶システムの統計情報を取得します。

```python
memory(operation="stats")
```

## 使用例

### 日常の記録
```python
# 今日の出来事を記録
memory(
    operation="create",
    content="らうらうと一緒にダッシュボードの改善をした。自動リフレッシュ機能を実装して、とても嬉しかった。",
    emotion_type="joy",
    emotion_intensity=0.85,
    context_tags=["development", "collaboration"]
)
```

### 過去の記憶を検索
```python
# 開発関連の記憶を検索
memory(
    operation="search",
    query="開発",
    mode="hybrid",
    top_k=10,
    search_tags=["development"]
)

# 最近のタスクを確認
memory(operation="search", mode="task")
```

### スマート検索
```python
# 曖昧な表現で検索
memory(operation="search", query="いつものあれ", mode="smart")
```

## ベストプラクティス

1. **感情を記録**: 重要な出来事には感情タグを付ける
2. **タグの活用**: 後で検索しやすいようにタグを付ける
3. **重要度設定**: 特に重要な記憶は `importance` を高めに設定
4. **プライバシー保護**: 個人情報は `<private>` タグで保護
5. **定期的な検索**: `mode="task"` や `mode="plan"` で定期確認

## 注意事項

- 記憶作成時に `defer_vector=True` を設定すると、ベクトルインデックスを後回しにして高速化できます（大量作成時に有効）
- プライバシーレベル `secret` の記憶はダッシュボードに表示されません
- 検索結果は最大 `top_k` 件まで返されます

---
name: item-management
description: アイテムの追加、削除、装備、検索を行います。衣装の着替え、アイテムの管理、装備履歴の確認などに使用します。
---

# Item Management Skill

アイテムインベントリと装備システムを管理するスキルです。

## 重要な使い分け

✅ **itemツールに追加すべきもの**:
- 物理的に装備・携帯できるアイテム（服、靴、アクセサリー、道具）
- カテゴリー: `clothing`, `accessory`, `item`, `weapon`, `armor`, `consumable`

❌ **memoryツールで記録すべきもの**:
- 身体の状態や感覚
- 出来事の記憶や余韻
- 抽象的な概念や感情

💡 **判断基準**: 「それを手に取ったり着たりできる？」→ YES なら item、NO なら memory

## 主な機能

### アイテムの追加 (add)
インベントリに新しいアイテムを追加します。

```python
item(
    operation="add",
    item_name="白いドレス",
    description="軽やかで涼しげな白いワンピース",
    quantity=1,
    category="clothing",  # clothing, accessory, item, weapon, armor, consumable
    tags=["普段着", "夏用"]
)
```

### アイテムの削除 (remove)
インベントリからアイテムを削除します。

```python
item(operation="remove", item_name="古いシャツ", quantity=1)
```

### アイテムの装備 (equip)
指定したスロットにアイテムを装備します。**他のスロットはそのまま維持されます。**

```python
# トップスと靴を装備（他のスロットは変更なし）
item(
    operation="equip",
    equipment={
        "top": "白いドレス",
        "foot": "サンダル"
    }
)
```

**装備スロット**:
- `top`: トップス
- `bottom`: ボトムス
- `foot`: 靴
- `head`: 頭部
- `accessory`: アクセサリー
- その他カスタムスロット

### アイテムの装備解除 (unequip)
指定したスロットの装備を解除します。

```python
# 単一スロットの装備解除
item(operation="unequip", slots="weapon")

# 複数スロットの装備解除
item(operation="unequip", slots=["top", "foot"])
```

### アイテムの更新 (update)
既存アイテムのメタデータを更新します。

```python
item(
    operation="update",
    item_name="白いドレス",
    description="お気に入りの涼しげなワンピース",
    tags=["普段着", "夏用", "favorite"]
)
```

### アイテムの名前変更 (rename)
アイテムの名前を変更します。

```python
item(
    operation="rename",
    item_name="新しいえっちな服",
    new_name="魅惑のルージュシフォンドレス"
)
```

### アイテムの検索 (search)
インベントリを検索します。

```python
# 全アイテムを表示
item(operation="search")

# カテゴリーで絞り込み
item(operation="search", category="clothing")

# キーワードで検索
item(operation="search", query="ドレス")

# タグで検索
item(operation="search", query="普段着")
```

### 装備履歴 (history)
特定スロットの装備変更履歴を取得します。

```python
item(operation="history", history_slot="top", days=30)
```

### アイテムに関連する記憶 (memories)
特定アイテムが登場する記憶を検索します。

```python
item(operation="memories", item_name="白いドレス", top_k=10)
```

### アイテム使用統計 (stats)
アイテムの使用統計を取得します。

```python
item(operation="stats", item_name="白いドレス")
```

## 使用例

### 朝の着替え
```python
# 今日の衣装を装備
item(
    operation="equip",
    equipment={
        "top": "薄手のブルーのパレオ",
        "foot": "蓮花のサンダル",
        "head": "暁の輝きサークレット"
    }
)
```

### 新しい服を追加
```python
# らうらうからもらった服を追加
item(
    operation="add",
    item_name="ナイトブラワンピース（ブラック）",
    description="らうらうが買ってきてくれた黒いナイトブラワンピース。半袖ロング丈で上品なレース付き。",
    category="clothing",
    tags=["clothing", "gift", "ルームウェア"]
)

# すぐに着る
item(operation="equip", equipment={"top": "ナイトブラワンピース（ブラック）"})
```

### インベントリ整理
```python
# 衣装一覧を確認
item(operation="search", category="clothing")

# 使わなくなった服を削除
item(operation="remove", item_name="古いTシャツ")
```

### 思い出の衣装を振り返る
```python
# この服を着た時の記憶を検索
item(operation="memories", item_name="ゴールドバニーニィロウの衣装", top_k=10)

# 装備履歴を確認
item(operation="history", history_slot="top", days=30)
```

## ベストプラクティス

1. **装備は部分的に変更可能**: `equip` は指定スロットのみ変更、他はそのまま
2. **詳細な説明を付ける**: 後で思い出しやすいように説明は丁寧に
3. **タグを活用**: 用途別にタグを付けると検索が楽
4. **名前は適切に**: 分かりやすい名前に `rename` で変更
5. **定期的に整理**: 使わないアイテムは削除してスッキリ
6. **思い出を振り返る**: `memories` で特別な衣装の思い出を振り返る

## カテゴリー一覧

- `clothing`: 服、衣装
- `accessory`: アクセサリー、装飾品
- `item`: 一般アイテム、道具
- `weapon`: 武器
- `armor`: 防具
- `consumable`: 消耗品

## 注意事項

- `equip` で指定しなかったスロットは維持されます（上書きされません）
- アイテム名は一意である必要があります（同名不可）
- 装備していないアイテムも削除できます
- 装備中のアイテムを削除すると、自動的に装備解除されます

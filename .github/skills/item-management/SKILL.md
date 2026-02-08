---
name: item-management
description: アイテムの追加、削除、装備、検索を行います。衣装の着替え、アイテムの管理、装備履歴の確認などに使用します。
---

# Item Management Skill

アイテムと装備を管理します。衣装の変更、持ち物の管理、装備履歴の確認ができます。

## 使い方

```bash
# アイテムを追加
python .github/skills/scripts/memory_mcp.py item add '{"item_name": "白いドレス", "description": "エレガントなロングドレス", "quantity": 1, "category": "clothing", "tags": ["formal", "white"]}'

# 装備する
python .github/skills/scripts/memory_mcp.py item equip '{"equipment": {"top": "白いドレス", "foot": "サンダル"}}'

# アイテム一覧
python .github/skills/scripts/memory_mcp.py item search

# カテゴリー検索
python .github/skills/scripts/memory_mcp.py item search '{"category": "clothing"}'
```

## 主な操作

### add - アイテムの追加
```bash
python .github/skills/scripts/memory_mcp.py item add '{
  "item_name": "白いドレス",
  "description": "エレガントなロングドレス",
  "quantity": 1,
  "category": "clothing",
  "tags": ["formal", "white"]
}'
```

**カテゴリー**: `clothing`, `accessory`, `item`, `weapon`, `armor`, `consumable`

### remove - アイテムの削除
```bash
python .github/skills/scripts/memory_mcp.py item remove '{
  "item_name": "白いドレス",
  "quantity": 1
}'
```

### equip - アイテムの装備
指定したスロットのみ変更し、他のスロットは維持されます。
```bash
python .github/skills/scripts/memory_mcp.py item equip '{
  "equipment": {
    "top": "白いドレス",
    "foot": "サンダル"
  }
}'
```

**装備スロット**: `head`, `top`, `bottom`, `foot`, `accessory`, `weapon`, etc.

### unequip - 装備解除
```bash
# 単一スロット
python .github/skills/scripts/memory_mcp.py item unequip '{"slots": "weapon"}'

# 複数スロット
python .github/skills/scripts/memory_mcp.py item unequip '{"slots": ["top", "foot"]}'
```

### update - アイテムの更新
```bash
python .github/skills/scripts/memory_mcp.py item update '{
  "item_name": "白いドレス",
  "description": "とても気に入っているエレガントなドレス"
}'
```

### rename - アイテムの名前変更
```bash
python .github/skills/scripts/memory_mcp.py item rename '{
  "item_name": "新しいえっちな服",
  "new_name": "魅惑のルージュシフォンドレス"
}'
```

### search - アイテム検索
```bash
# 全アイテム表示
python .github/skills/scripts/memory_mcp.py item search

# カテゴリーで絞り込み
python .github/skills/scripts/memory_mcp.py item search '{"category": "clothing"}'

# キーワード検索
python .github/skills/scripts/memory_mcp.py item search '{"query": "ドレス"}'
```

### history - 装備履歴
```bash
python .github/skills/scripts/memory_mcp.py item history '{
  "history_slot": "top",
  "days": 30
}'
```

### memories - アイテムに関連する記憶
```bash
python .github/skills/scripts/memory_mcp.py item memories '{
  "item_name": "白いドレス",
  "top_k": 10
}'
```

### stats - 使用統計
```bash
python .github/skills/scripts/memory_mcp.py item stats '{
  "item_name": "白いドレス"
}'
```

## 使用例

### 新しい衣装の追加と装備
```bash
# 1. 新しいドレスを追加
python .github/skills/scripts/memory_mcp.py item add '{
  "item_name": "青いドレス",
  "description": "涼しげな夏のドレス",
  "category": "clothing",
  "tags": ["summer", "blue", "casual"]
}'

# 2. 装備する
python .github/skills/scripts/memory_mcp.py item equip '{"equipment": {"top": "青いドレス"}}'
```

### 状況に応じた着替え
```bash
# カジュアルな服装
python .github/skills/scripts/memory_mcp.py item equip '{
  "equipment": {
    "top": "Tシャツ",
    "bottom": "ジーンズ",
    "foot": "スニーカー"
  }
}'

# フォーマルな服装
python .github/skills/scripts/memory_mcp.py item equip '{
  "equipment": {
    "top": "白いドレス",
    "foot": "ハイヒール",
    "accessory": "ネックレス"
  }
}'
```

## コツ

1. **カテゴリー分類** - アイテム追加時は適切なカテゴリーを設定
2. **タグ活用** - 検索しやすいようにタグを付ける
3. **装備の一貫性** - 状況に合った装備セットを使用
4. **定期的な確認** - `search` で現在の所持品を確認
5. **履歴の活用** - `history` で過去の装備パターンを分析

## 注意事項

**物理アイテムのみ**を追加してください：
- ✅ 追加すべき: 服、靴、アクセサリー、道具
- ❌ 追加しない: 体の状態、感覚、感情、記憶（これらは `memory` ツールで管理）

💡 **判断基準**: 「それを手に取ったり着たりできる？」→YES なら item、NO なら memory

- `equip` は指定したスロットのみ変更し、他のスロットは維持されます
- `unequip` で装備を外すとスロットは空になります

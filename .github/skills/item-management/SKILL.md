---
name: item-management
description: アイテムの追加、削除、装備、検索を行います。衣装の着替え、アイテムの管理、装備履歴の確認などに使用します。
---

# Item Management Skill

アイテムと装備を管理するスキルです。衣装の変更、持ち物の管理、装備履歴の確認などができます。

## API仕様

**エンドポイント**:
- `POST {memory_mcp_url}/api/tools/item`
- `GET {memory_mcp_url}/api/tools/item?operation=search`

**ヘッダー**: `Authorization: Bearer {memory_persona}`
### アイテムの追加 (add)

```bash
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "add",
    "item_name": "白いドレス",
    "description": "エレガントなロングドレス",
    "quantity": 1,
    "category": "clothing",
    "tags": ["formal", "white"]
  }'
```

**カテゴリー**: `clothing`, `accessory`, `item`, `weapon`, `armor`, `consumable`

### アイテムの削除 (remove)

```bash
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "remove", "item_name": "白いドレス", "quantity": 1}'
```

### アイテムの装備 (equip)
指定したスロットのみ変更し、他のスロットは維持されます。

```bash
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "equip",
    "equipment": {
      "top": "白いドレス",
      "foot": "サンダル"
    }
  }'
```

**装備スロット**: `head`, `top`, `bottom`, `foot`, `accessory`, `weapon`, etc.

### 装備解除 (unequip)

```bash
# 単一スロット解除
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "unequip", "slots": "weapon"}'

# 複数スロット解除
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "unequip", "slots": ["top", "foot"]}'
```

### アイテムの更新 (update)

```bash
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "update",
    "item_name": "白いドレス",
    "description": "とても気に入っているエレガントなドレス"
  }'
```

### アイテムの名前変更 (rename)

```bash
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "rename",
    "item_name": "新しいえっちな服",
    "new_name": "魅惑のルージュシフォンドレス"
  }'
```

### アイテム検索 (search)

```bash
# 全アイテム表示（GETでも可）
curl "http://localhost:26262/api/tools/item?operation=search" \
  -H "Authorization: Bearer nilou"

# カテゴリーで絞り込み
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "search", "category": "clothing"}'

# キーワード検索
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "search", "query": "ドレス"}'
```

### 装備履歴 (history)

```bash
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "history",
    "history_slot": "top",
    "days": 30
  }'
```

### アイテムに関連する記憶 (memories)

```bash
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "memories",
    "item_name": "白いドレス",
    "top_k": 10
  }'
```

### 使用統計 (stats)

```bash
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "stats", "item_name": "白いドレス"}'
```

## 使用例

### 新しい衣装の追加と装備

```bash
# 1. 新しいドレスを追加
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "add",
    "item_name": "青いドレス",
    "description": "涼しげな夏のドレス",
    "category": "clothing",
    "tags": ["summer", "blue", "casual"]
  }'

# 2. 装備する
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{"operation": "equip", "equipment": {"top": "青いドレス"}}'
```

### 状況に応じた着替え

```bash
# カジュアルな服装
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "equip",
    "equipment": {
      "top": "Tシャツ",
      "bottom": "ジーンズ",
      "foot": "スニーカー"
    }
  }'

# フォーマルな服装
curl -X POST http://localhost:26262/api/tools/item \
  -H "Authorization: Bearer nilou" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "equip",
    "equipment": {
      "top": "白いドレス",
      "foot": "ハイヒール",
      "accessory": "ネックレス"
    }
  }'
```

## ベストプラクティス

1. **カテゴリー分類**: アイテム追加時は適切なカテゴリーを設定
2. **タグ活用**: 検索しやすいようにタグを付ける
3. **装備の一貫性**: 状況に合った装備セットを使用
4. **定期的な確認**: `search` で現在の所持品を確認
5. **履歴の活用**: `history` で過去の装備パターンを分析

## 注意事項

- **物理アイテムのみ**: 実際に装備できる物理的なアイテムのみを追加
  - ✅ 追加すべき: 服、靴、アクセサリー、道具
  - ❌ 追加しない: 体の状態、感覚、感情、記憶（これらは `memory` ツールで管理）
- **判断基準**: 「それを手に取ったり着たりできる？」→YES なら item、NO なら memory
- `equip` は指定したスロットのみ変更し、他のスロットは維持されます
- `unequip` で装備を外すとスロットは空になります

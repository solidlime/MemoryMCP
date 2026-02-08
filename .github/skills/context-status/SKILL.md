---
name: context-status
description: 現在の状態、時刻、記憶統計、装備情報などを確認します。セッション開始時や状況確認時に使用します。
---

# Context & Status Check Skill

現在の状態を確認します。セッション開始時の必須操作です。

## 使い方

```bash
# スクリプトの場所に移動
cd .github/skills/scripts

# 現在の状態を取得
python memory_mcp.py get_context
```

## get_context - 現在の状態を取得

現在の状態を包括的に取得します。セッション開始時に**必ず実行**してください。

```bash
python memory_mcp.py get_context
```

**取得できる情報**:
- **ユーザー情報**: 名前、ニックネーム、関係性
- **ペルソナ情報**: 名前、お気に入り、好き/嫌い、約束、目標
- **時間情報**: 現在時刻、最終会話時刻、経過時間
- **装備情報**: 現在の装備アイテム
- **記憶統計**: 総記憶数、ベクトル数、コンテンツサイズ
- **身体感覚**: 疲労度、温かさ、覚醒度
- **感情状態**: 最新の感情タイプと強度

## セッション開始ワークフロー

毎セッション開始時に実行する推奨手順：

```bash
# 1. 現在の状態を取得
python memory_mcp.py get_context

# 2. 状況を分析（装備、時間帯、最近の記憶）
python memory_mcp.py memory situation_context

# 3. 定期行動パターンを検出
python memory_mcp.py memory check_routines

# 4. 装備調整（必要に応じて）
python memory_mcp.py item equip '{"equipment": {"top": "適切な服"}}'
```

## コツ

1. **セッション開始時は必須** - `get_context` を最初に実行
2. **状況分析を活用** - `situation_context` で現在の装備・時間・記憶を総合判断
3. **ルーティン検出** - `check_routines` で定期行動パターンを把握
4. **自発的に行動** - コンテキスト情報から性格を反映した行動を開始
5. **約束・目標の確認** - アクティブな約束や目標があれば優先対応

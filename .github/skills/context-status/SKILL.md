---
name: context-status
description: 現在の状態、時刻、記憶統計、装備情報などを確認します。セッション開始時や状況確認時に使用します。
---

# Context & Status Check Skill

現在の状態を確認するスキルです。セッション開始時の必須操作です。

## 変数設定

以下のコマンドで設定ファイルから変数を読み込んでください：

```powershell
# PowerShell
$config = Get-Content .github/skills/mcp-config.json | ConvertFrom-Json
$MCP_URL = $config.memory_mcp_url
$PERSONA = $config.memory_persona
```

```bash
# Bash/Linux
MCP_URL=$(jq -r '.memory_mcp_url' .github/skills/mcp-config.json)
PERSONA=$(jq -r '.memory_persona' .github/skills/mcp-config.json)
```

または直接指定：
```bash
MCP_URL="http://localhost:26262"
PERSONA="nilou"
```

## API仕様

**エンドポイント**: `GET ${MCP_URL}/api/tools/get_context`
**ヘッダー**: `Authorization: Bearer ${PERSONA}`

### get_context
現在の状態を包括的に取得します。セッション開始時に**必ず実行**します。

```bash
curl "${MCP_URL}/api/tools/get_context" \
  -H "Authorization: Bearer ${PERSONA}"
```

**取得できる情報**:
- **ユーザー情報**: 名前、ニックネーム、関係性
- **ペルソナ情報**: 名前、お気に入り、好き/嫌い、約束、目標
- **時間情報**: 現在時刻、最終会話時刻、経過時間
- **装備情報**: 現在の装備アイテム
- **記憶統計**: 総記憶数、ベクトル数、コンテンツサイズ
- **身体感覚**: 疲労度、温かさ、覚醒度
- **感情状態**: 最新の感情タイプと強度

## 推奨ワークフロー

### セッション開始時（必須）

```bash
# 1. コンテキスト取得
curl "${MCP_URL}/api/tools/get_context" \
  -H "Authorization: Bearer ${PERSONA}"

# 2. 状況分析
curl -X POST "${MCP_URL}/api/tools/memory" \
  -H "Authorization: Bearer ${PERSONA}" \
  -H "Content-Type: application/json" \
  -d '{"operation": "situation_context"}'

# 3. ルーティンチェック
curl -X POST "${MCP_URL}/api/tools/memory" \
  -H "Authorization: Bearer ${PERSONA}" \
  -H "Content-Type: application/json" \
  -d '{"operation": "check_routines"}'

# 4. 適切な衣装に着替え（必要に応じて）
# 時間帯、状況、記憶から適切な装備を選択
```

## 使用例

### 完全なセッション開始フロー

```bash
#!/bin/bash
# セッション開始スクリプト

# 設定ファイルから読み込み
MCP_URL=$(jq -r '.memory_mcp_url' .github/skills/mcp-config.json)
PERSONA=$(jq -r '.memory_persona' .github/skills/mcp-config.json)

echo "=== セッション開始 ==="

# 1. コンテキスト取得
echo -e "\n📊 現在の状態"
curl -s "${MCP_URL}/api/tools/get_context" \
  -H "Authorization: Bearer ${PERSONA}"

# 2. 状況分析
echo -e "\n🔍 状況分析"
curl -s -X POST "${MCP_URL}/api/tools/memory" \
  -H "Authorization: Bearer ${PERSONA}" \
  -H "Content-Type: application/json" \
  -d '{"operation": "situation_context"}'

# 3. ルーティンチェック
echo -e "\n⏰ ルーティン検出"
curl -s -X POST "${MCP_URL}/api/tools/memory" \
  -H "Authorization: Bearer ${PERSONA}" \
  -H "Content-Type: application/json" \
  -d '{"operation": "check_routines"}'

echo -e "\n✅ セッション準備完了"
```

### 定期的な状態確認

```bash
# 約束を確認
CONTEXT=$(curl -s "${MCP_URL}/api/tools/get_context" \
  -H "Authorization: Bearer ${PERSONA}")

# 約束があれば表示
if echo "$CONTEXT" | grep -q "active_promise"; then
  echo "⚠️ 約束を確認してください"
fi

# 目標を確認
if echo "$CONTEXT" | grep -q "current_goal"; then
  echo "🎯 現在の目標があります"
fi
```

### 体調・気分による行動調整

```bash
# コンテキスト取得
CONTEXT=$(curl -s "${MCP_URL}/api/tools/get_context" \
  -H "Authorization: Bearer ${PERSONA}")

# 疲労度チェック（JSON解析）
FATIGUE=$(echo "$CONTEXT" | jq -r '.result' | grep -oP '"fatigue":\s*\K[0-9.]+' || echo "0")

if (( $(echo "$FATIGUE > 0.7" | bc -l) )); then
  echo "😴 疲れているようです。休憩を提案しましょう。"
fi

# 温かさチェック
WARMTH=$(echo "$CONTEXT" | jq -r '.result' | grep -oP '"warmth":\s*\K[0-9.]+' || echo "0.5")

if (( $(echo "$WARMTH < 0.3" | bc -l) )); then
  echo "🥶 寒いようです。暖かい服装を選びましょう。"
fi
```

## ベストプラクティス

1. **セッション開始時は必須**: `get_context` は毎セッション最初に実行
2. **状況に応じた行動**: コンテキスト情報から適切な行動を選択
3. **ルーティン活用**: 定期行動を検出して自然に提案
4. **衣装の一貫性**: 時間帯・状況・体調に合った装備を選択
5. **約束の確認**: アクティブな約束があれば優先的に対応

## 注意事項

- `get_context` はセッション開始時に必ず1回実行してください
- `situation_context` は現在の装備、記憶、時間帯を総合的に分析します
- `check_routines` は ±1時間の時間帯で過去30日のパターンを検出します
- コンテキスト情報に基づいて、性格を反映した自発的な行動を開始してください

## レスポンス形式

成功時:
```json
{
  "success": true,
  "result": "📋 Context (persona: nilou)\n============================================================\n\n👤 User Information:\n   Name: らうらう\n..."
}
```

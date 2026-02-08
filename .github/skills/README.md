# Memory MCP Skills for GitHub Copilot

Memory MCPの機能をGitHub Copilot Skillsとして利用するための設定です。

## 📚 利用可能なスキル

### 1. **memory-operation** - 記憶の基本操作
記憶の作成、読み込み、検索、更新、削除を行います。
- 日常の出来事を記録
- 過去の記憶を検索
- タスクや予定の管理

### 2. **memory-context** - コンテキスト管理
約束、目標、お気に入り、感情、身体感覚などを管理します。
- 約束や目標の設定
- 感情や身体状態の記録
- 記念日の管理
- お気に入りの追加

### 3. **item-management** - アイテム管理
アイテムの追加、削除、装備、検索を行います。
- 衣装の着替え
- インベントリ管理
- 装備履歴の確認

### 4. **context-status** - 状態確認
現在の状態、時刻、記憶統計、装備情報を確認します。
- セッション開始時の状態確認
- ルーティンチェック
- 状況分析

## 🚀 セットアップ

### 1. VS Code設定を有効化

`settings.json` で以下を設定：

```json
{
  "chat.useClaudeSkills": true
}
```

### 2. スキルの配置

このプロジェクトでは `.github/skills/` 配下にスキルが配置されています。

**個人スキル**（全プロジェクトで利用）:
```
~/.github/skills/<skill-name>/SKILL.md
```

**プロジェクトスキル**（このプロジェクトのみ）:
```
${workspaceFolder}/.github/skills/<skill-name>/SKILL.md
```

### 3. 使い方

スキルは自動的に認識され、`description` に基づいて適切なタイミングで呼び出されます。

**自動呼び出し例**:
- 「今日の出来事を記録して」→ **memory-operation** が呼び出される
- 「お気に入りに追加して」→ **memory-context** が呼び出される
- 「着替えよう」→ **item-management** が呼び出される
- 「現在の状態は？」→ **context-status** が呼び出される

**手動呼び出し**:
スラッシュコマンドとしても使用可能（実装されている場合）。

## 💡 推奨ワークフロー

### セッション開始時

```
1. 現在の状態を確認して
2. ルーティンをチェック
3. 今日の目標を設定
```

これにより：
- `context-status` で状態確認
- `memory-operation` でルーティンチェック
- `memory-context` で目標設定

### 日常的な使用

```
今日、らうらうと一緒にダッシュボードを改善したことを記録して。
とても嬉しかった。
```

→ **memory-operation** が自動的に呼び出され、適切に記憶が作成されます。

### 着替え

```
白いドレスとサンダルに着替える
```

→ **item-management** が自動的に呼び出され、装備が変更されます。

## 🎯 トークン削減効果

従来のMCPツールでは、全てのツール定義が毎回コンテキストに含まれていましたが、Skillsを使用することで：

### 従来（MCPツール）
- ツール定義全体がコンテキストに含まれる
- 推定: 約5,000〜10,000トークン/リクエスト

### Skills化後
- スキル説明のみがコンテキストに含まれる
- フルコンテンツは呼び出し時のみロード
- 推定: 約500〜1,000トークン/リクエスト（説明文のみ）

**削減率: 約80〜90%のトークン削減**

## 📖 各スキルの詳細

各スキルの詳細な使い方は、それぞれの `SKILL.md` を参照してください：

- [memory-operation/SKILL.md](./memory-operation/SKILL.md)
- [memory-context/SKILL.md](./memory-context/SKILL.md)
- [item-management/SKILL.md](./item-management/SKILL.md)
- [context-status/SKILL.md](./context-status/SKILL.md)

## ⚠️ 注意事項

1. **モデル依存**: Skillsの自動呼び出しはモデルによって効果が異なります
   - Claude Sonnet 4.5: 良好に動作
   - Claude Haiku 4.5: 明示的な指示が必要な場合あり

2. **VS Codeバージョン**:
   - Version 1.107以降で `chat.useClaudeSkills` が利用可能
   - Version 1.108以降で Agent Skills が正式サポート

3. **互換性**:
   - `.claude/skills/` は下位互換として動作しますがレガシー扱い
   - `.github/skills/` が推奨

## 🔧 トラブルシューティング

### スキルが認識されない

1. `chat.useClaudeSkills` が有効になっているか確認
2. スキルディレクトリが正しいか確認（`.github/skills/`）
3. `SKILL.md` に `description` が含まれているか確認

### スキルが呼び出されない

1. より明確に指示する（例: 「memory-operationを使って記録して」）
2. スキルの `description` を確認し、それに合う表現を使う
3. モデルを変更してみる（Claude Sonnet 4.5推奨）

## 📚 参考資料

- [Claude Code Skills Documentation](https://code.claude.com/docs/ja/skills)
- [VS Code November 2025 Release](https://code.visualstudio.com/updates/v1_107#_reuse-your-claude-skills-experimental)
- [Anthropic Skills Repository](https://github.com/anthropics/skills)

## 🤝 貢献

スキルの改善提案や新しいスキルのアイデアがあれば、ぜひIssueまたはPull Requestを作成してください！

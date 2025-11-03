# Testing Guide for Memory MCP

このドキュメントは、Memory MCPのローカルテスト環境のセットアップと使用方法を説明します。

## ローカルテスト環境のセットアップ

### 1. テスト用Persona作成

本番環境（`nilou`）を壊さないように、テスト専用のpersonaを使用します。

```bash
# 環境変数でテスト用personaを指定
export MEMORY_MCP_PERSONA=test

# または、起動時に指定
MEMORY_MCP_PERSONA=test uvicorn memory_mcp:mcp --host 0.0.0.0 --port 8000
```

### 2. テスト用データベース

テスト用personaを使用すると、以下の場所に独立したデータベースが作成されます：
- SQLite: `memory/test/memory.sqlite`
- Persona Context: `memory/test/persona_context.json`

### 3. テスト用Qdrantコレクション

Qdrantには `memory_test` というコレクションが作成されます。本番の `memory_nilou` とは完全に分離されます。

## Phase 28.2 のテスト手順

### 連想生成モジュールのテスト

1. **テスト用記憶の作成**
   ```python
   # 最初の記憶（ベースライン）
   create_memory("[[Python]]でWebスクレイピングを学んでいる", 
                 emotion_type="joy",
                 emotion_intensity=0.6,
                 importance=0.7)
   
   # 関連する記憶（類似記憶が自動リンクされるはず）
   create_memory("[[Python]]の[[Beautiful Soup]]ライブラリを使った",
                 emotion_type="joy", 
                 emotion_intensity=0.7,
                 importance=0.75)
   
   # 別トピックの記憶（リンクされないはず）
   create_memory("今日は[[イチゴ]]のケーキを食べた",
                 emotion_type="joy",
                 emotion_intensity=0.5,
                 importance=0.5)
   ```

2. **related_keysの確認**
   ```python
   # 2番目の記憶のrelated_keysに1番目の記憶が含まれているか確認
   read_memory("Beautiful Soup")
   # 期待される結果: related_keys に最初の記憶のkeyが含まれる
   ```

3. **感情強度による重要度補正の確認**
   ```python
   # 高emotion_intensity → importanceが自動的に補正されるはず
   create_memory("[[Phase 28]]の実装が完了した!", 
                 emotion_type="joy",
                 emotion_intensity=0.9,  # 非常に強い感情
                 importance=0.7)  # 基礎importance
   # 期待される結果: importance = 0.7 + (0.9 * 0.2) = 0.88
   ```

## テストデータのクリーンアップ

テスト後は以下のコマンドでデータをクリーンアップできます：

```bash
# テスト用データベースの削除
rm -rf memory/test/

# テスト用Qdrantコレクションの削除
# Admin Tools → Rebuild Qdrant Collection (persona: test)
# または直接APIで削除
```

## 本番環境への適用

テストが成功したら、本番環境（`nilou`）でも同じ機能が使えます：

```bash
# 本番環境に戻す
export MEMORY_MCP_PERSONA=nilou
# または環境変数を削除
unset MEMORY_MCP_PERSONA
```

## 注意事項

- **絶対にテスト中に本番環境のpersonaを使用しないこと**
- テスト用データは `.gitignore` に含まれているため、Gitにコミットされません
- Phase 28の新機能は既存の記憶に影響を与えないように設計されています（後方互換性）
- 自動マイグレーションにより、既存の記憶には `emotion_intensity=0.0`, `related_keys=[]`, `summary_ref=None` がデフォルトで設定されます

## Phase 28.2 実装チェックリスト

- [ ] `tools/association.py` の作成
- [ ] `create_memory()` での類似検索（top-3）実装
- [ ] `related_keys` の自動保存
- [ ] 感情強度による重要度補正
- [ ] テスト記憶での動作確認
- [ ] 本番環境での慎重な検証

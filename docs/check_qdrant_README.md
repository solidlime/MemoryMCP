# Qdrant Connection Verification Tool

本番環境のQdrantサーバーへの接続確認と状態チェックを行うCLIツールです。

## 機能

- ✅ Qdrantサーバーへの接続確認
- 📊 コレクション一覧の取得
- 📈 各コレクションのベクトル数表示
- 🔧 ベクトルサイズと距離メトリックの確認
- 💔 エラー時のトラブルシューティングヒント表示

## 使い方

### 基本的な使い方

```bash
# 本番環境（nas:6333）への接続確認
python3 check_qdrant.py http://nas:6333

# ローカル環境への接続確認
python3 check_qdrant.py http://localhost:6333

# 設定ファイル（config.json）から自動取得
python3 check_qdrant.py
```

### API キーを使用する場合

```bash
python3 check_qdrant.py http://nas:6333 your-api-key
```

### ヘルプの表示

```bash
python3 check_qdrant.py --help
```

## 関連ファイル

- `check_qdrant.py`: 本体
- `.vscode/tasks.json`: VS Code タスク定義
- `README.md`: プロジェクト全体のドキュメント
- `DOCKER.md`: Docker環境での使用方法

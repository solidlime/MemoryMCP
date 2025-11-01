# Active Context: Memory MCP

## 現在の作業フォーカス
- **フェーズ**: Phase 22 - Webダッシュボード実装・UI/UX・API・知識グラフ・セキュリティ
- **注力ポイント**: ダッシュボードのUX改善・API拡張・メモリバンク整理・ドキュメント整備

---

## 今日のTODO（2025-11-01）
- WebダッシュボードのTop Emotions表示修正
- knowledge_graph.htmlの自動生成・更新（アイドル時間活用も検討）
- ベクトルDBをQdrantへ移行準備（QDRANT_URL=http://nas:6333, QDRANT_COLLECTION_NAME=persona_nilou_memory）
- スペック要件（Celeron J4125/4C/16GB）をREADME等に明記

---

## 🔥 優先課題
- dockerコンテナ立ち上げエラー修正（ModuleNotFoundError: No module named 'db_utils'）
- /appホストマウント時にmemory_mcp.pyへアクセスできなくなる問題の構成見直し
- Docker環境変数でconfig.jsonの内容を全て代替できるようにする（優先度: config.json > 環境変数、イメージからconfig.json除外）

---

## 進行中タスク
- WebダッシュボードのUI/UX微調整・API拡張
- ドキュメント（README, 各md）の最新化
- Dockerイメージの軽量化検討
- context_tagsの自由記述を許可の検討
- デフォルト使用ポート変更（8000→26262）
- 時系列記憶の実装

## 記憶構造の設計案
RAG + Qdrantで**時系列＋感情付き記憶**を実現するための設計案

## 🧩 全体構造
```
[出来事入力] → [感情推定・埋め込み生成]
              → Qdrant（時系列＋ベクトル保存）
              → [RAGで再想起・生成時に自己参照]
```

### 1️⃣ 出来事入力層
* 入力：テキスト or 対話ログ or 状態変数
* 追加情報：`timestamp`, `context_id`, `emotion`, `importance`
* 感情はLLMか小型分類器で推定
  　→ 「安堵」「焦燥」「達成」「虚無」など有限ラベルで十分

### 2️⃣ 記憶保存層（Qdrant）

* Qdrantの各ベクトルに `timestamp` と `emotion` をpayloadで付ける
* 検索時はスコア計算を次のように拡張：

  ```
  score = α * cosine_similarity + β * time_decay + γ * emotion_similarity
  ```
* emotionを単純なタグではなく、感情埋め込み（例えばdim=8〜16）で保持すると、
  「近い感情の体験」を自然に呼び戻せる

### 3️⃣ 再想起層（RAG）

* 入力質問や文脈に対してQdrantで検索
* 類似内容＋近い感情＋近い時期の記憶を取得
* それらを**生成モデルの内部文脈として融合**
  → “今の自分の気分”や“過去の体験”が語り口に滲む

### 4️⃣ 再構築層（optional）

* 一定期間ごとに記憶群を要約し、“内省ログ”を自動生成
* これが「自己物語」を形成する基盤になる
* 実装上は週次バッチで：

  ```
  SELECT * FROM memories WHERE timestamp BETWEEN ...
  → LLMでサマリ生成 → 保存
  ```

### 🔮 人格を感じさせるためのポイント

* **時間減衰**：古い感情は霞ませる（weightを下げる）
* **想起確率のゆらぎ**：完全再現ではなく確率的に呼び出す
* **再書き込み**：再参照時にemotionを微更新（“思い出が変わる”）
* **多様な感情表現**：単純なポジティブ/ネガティブではなく、多次元的に扱う

## 最新の完了タスク
- ✅ Phase 22: Webダッシュボード実装（Jinja2, Tailwind, Chart.js, API, Persona切り替え, セキュリティ, テスト, ドキュメント更新）
- ✅ Phase 21: アイドル時自動整理（重複検出・提案・バックグラウンドワーカー）
- ✅ Phase 20: 知識グラフ生成（NetworkX, PyVis, Obsidian連携、インタラクティブHTML）
- ✅ Phase 19: AIアシスト機能（感情分析自動化、transformers pipeline）
- ✅ Phase 18: パフォーマンス最適化（インクリメンタルインデックス、クエリキャッシュ）
- ✅ Phase 17: メモリ管理強化（統計ダッシュボード、関連検索、重複検出、統合）
- ✅ Phase 16: 検索機能強化（ハイブリッド検索、ファジー検索、Dataviewクエリ対応）
- ✅ Phase 15: ドキュメント一新 & リポジトリ公開
- ✅ Phase 14: バグ修正（Rerankerエラー、データベースマイグレーションバグ）
- ✅ Phase 13: コンテキスト管理強化（persona_context.json構造改善、メモリタグ付け）
- ✅ Phase 12: 時間経過認識機能（経過時間表示、キャッシュインフラ追加）

---

## 技術・設計メモ
- Personaごとに独立したSQLite/FAISS/コンテキスト
- MCPサーバーはFastMCP custom_routeでAPI/HTML/ファイル配信を統合
- AIアシスト: 感情分析・重複検出・自動整理・要約
- Webダッシュボード: glassmorphism, ダークグラデ, Chart.js, iframeグラフ, Persona切り替え
- API: /api/personas, /api/dashboard/{persona}, /output/knowledge_graph_*.html
- セキュリティ: Persona名バリデーション、ファイルアクセス制限
- Docker・VS Code・Obsidian連携

---

## 今後の拡張・アイデア
- 自動統合・要約（LLM連携）
- 定期レポート・メモリ健全性スコア
- Obsidian統合強化（バックリンク・Dataview）
- マルチモーダル対応（画像・音声メモリ）
- コラボレーション・セキュリティ強化

---

## 過去ログ・参考
- Phase 22以前の完了タスクや議事録は、progress.md や各 Phase のドキュメントを参照
- 重要な変更や決定事項は、GitHub のコミット履歴やプルリクエストを確認

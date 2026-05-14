# TODO - タスクリスト

## 優先度：高

### P1: date_range 検索フィルタ統合
- [ ] T001: Repository Protocol に `date_from`, `date_to` パラメータ追加（`domain/memory/repository.py`）
- [ ] T002: KeywordSearchStrategy / SemanticSearchStrategy Protocol に date パラメータ追加（`domain/search/strategies.py`）
- [ ] T003: SQLite `search_keyword()` に日付フィルタ追加 + インデックス確認（`infrastructure/sqlite/memory_repo.py`）
- [ ] T004: Qdrant `search()` に payload filter 追加（`infrastructure/qdrant/adapter.py`）
- [ ] T005: Adapter 層で date パラメータのパススルー（`application/use_cases.py`）
- [ ] T006: SearchEngine で `parse_date_range()` を実行し各戦略に渡す（`domain/search/engine.py`）
- [ ] T007: P1 ユニットテスト作成（SQLite日付フィルタ、Qdrantフィルタ、パース境界値）

### P2+P3: 記憶エンリッチメント（重要度 + 関係性自動抽出）
- [ ] T008: `EnrichmentResult` データクラス作成（`domain/memory/enrichment.py`）
- [ ] T009: `MemoryEnricher` LLM 呼出実装（`infrastructure/llm/memory_enricher.py`）
- [ ] T010: `MemoryService.create_memory()` に enrichment 統合（`domain/memory/service.py`）
- [ ] T011: 設定追加 `memory_enrichment_enabled`, `enrichment_min_chars`（`config/settings.py`）
- [ ] T012: P2+P3 ユニットテスト作成（LLMモック、importanceスキップ、short skip）

### P4: メンタルモデル抽象化
- [ ] T013: `MentalModel` エンティティ + `PatternDetector` 作成（`domain/memory/mental_model.py`, `application/chat/pattern_detector.py`）
- [ ] T014: ReflectionEngine にパターン抽象化ロジック追加（`application/chat/reflection.py`）
- [ ] T015: 設定追加 `mental_model_enabled`, `mental_model_min_samples`（`config/settings.py`）
- [ ] T016: P4 ユニットテスト作成（パターン検出トリガー、LLMモック）

## 優先度：中
- [ ] T017: 全テスト実行・CI確認（Unit + Integration + E2E）

## 優先度：低
- [ ] T018: SPEC.md / KNOWLEDGE.md に実装結果反映

## 完了済み
- [x] SPEC.md 作成（P1〜P4 統合設計）

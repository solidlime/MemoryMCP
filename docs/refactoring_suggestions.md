# コードリファクタリング提案書

## 実施済みの改善 ✅

### 1. 重複インポートの修正
- **ファイル**: `src/utils/vector_utils.py`
- **問題**: `import os` が1行目と3行目で重複
- **修正**: 重複を削除し、インポートを整理

### 2. グローバル変数の整理
- **ファイル**: `src/utils/vector_utils.py`
- **問題**: 多数のグローバル変数が散在し、状態管理が不明確
- **修正**: `VectorStoreState` クラスを導入
  - すべてのRAG関連の状態を一つのクラスに集約
  - スレッドロックを含む全ての状態変数をプロパティとして管理
  - 後方互換性のため、レガシー変数も保持

#### 改善内容
```python
# 【改善前】バラバラのグローバル変数
embeddings = None
reranker = None
_dirty = False
_last_write_ts = 0.0
_rebuild_lock = threading.Lock()
# ... など大量のグローバル変数

# 【改善後】状態管理クラス
class VectorStoreState:
    def __init__(self):
        self.embeddings = None
        self.reranker = None
        self._dirty = False
        # ...全ての状態を集約

    def mark_dirty(self):
        """Mark vector store as dirty (needs rebuild)."""
        self._dirty = True
        self._last_write_ts = time.time()
```

**利点**:
- 状態管理が明確になり、テストが容易に
- スレッドセーフな操作がメソッドとして提供される
- 将来的に複数のペルソナや環境での並列処理が容易に

---

## 推奨する追加改善 💡

### 3. 長い関数の分割（優先度: 高）

#### 3.1 `tools/crud_tools.py` - `get_memory_stats()` (約150行)
**問題**: 統計計算、フォーマット、データ取得が全て一つの関数に混在

**提案**: 統計データクラスの導入
```python
from dataclasses import dataclass
from typing import List, Dict, Tuple

@dataclass
class MemoryStatistics:
    """Memory statistics data container."""
    total_count: int
    total_chars: int
    date_range: Tuple[str, str]
    avg_importance: float
    min_importance: float
    max_importance: float
    high_importance_count: int
    medium_importance_count: int
    low_importance_count: int
    emotion_counts: List[Tuple[str, int]]
    tag_counts: Dict[str, int]
    recent_memories: List[Tuple]

    @classmethod
    def from_database(cls, db_path: str, persona: str) -> 'MemoryStatistics':
        """Factory method to create statistics from database."""
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # データ取得ロジック
            return cls(...)

    def format_display(self, persona: str) -> str:
        """Format statistics for display."""
        result = f"📊 Memory Statistics (persona: {persona})\n\n"
        # フォーマットロジック
        return result
```

**利点**:
- データ取得、計算、表示が分離される
- テストが容易になる
- 統計データの再利用が可能（API、ダッシュボード等）

#### 3.2 `tools/crud_tools.py` - `create_memory()` (約140行)
**問題**: 検証、保存、コンテキスト更新、履歴保存が一つの関数に集中

**提案**: メモリ作成プロセスのクラス化
```python
class MemoryCreator:
    """Handles memory creation workflow."""

    def __init__(self, persona: str):
        self.persona = persona
        self.db_path = get_db_path()

    def create(self, content: str, **kwargs) -> str:
        """Main creation workflow."""
        # 1. Validate and prepare
        memory_data = self._prepare_memory_data(content, **kwargs)

        # 2. Save to stores
        self._save_to_stores(memory_data)

        # 3. Update context
        self._update_context(memory_data)

        # 4. Save history
        self._save_history(memory_data)

        # 5. Format result
        return self._format_result(memory_data)

    def _prepare_memory_data(self, content, **kwargs):
        """Prepare memory data with validation."""
        # データ準備ロジック
        pass

    # 他のプライベートメソッド...
```

**利点**:
- 各ステップが独立したメソッドとして明確に
- エラーハンドリングが各段階で可能
- テストが段階ごとに可能

### 4. 型ヒントの追加（優先度: 中）

**問題**: 多くの関数で型ヒントが不完全または欠如

**提案**:
```python
# 【改善前】
def _calculate_final_score(base_score, meta, importance_weight, recency_weight):
    """Calculate final score including importance, recency, and access frequency."""
    ...

# 【改善後】
def _calculate_final_score(
    base_score: float,
    meta: Dict[str, Any],
    importance_weight: float,
    recency_weight: float
) -> float:
    """Calculate final score including importance, recency, and access frequency.

    Args:
        base_score: Base similarity score (0.0-1.0)
        meta: Document metadata dictionary
        importance_weight: Weight for importance scoring (0.0-1.0)
        recency_weight: Weight for recency scoring (0.0-1.0)

    Returns:
        Final weighted score
    """
    ...
```

**対象ファイル**:
- `tools/crud_tools.py`
- `tools/search_tools.py`
- `tools/analysis_tools.py`

### 5. 定数の集約（優先度: 中）

**問題**: マジックナンバーや文字列リテラルが散在

**提案**: `core/constants.py` を作成
```python
"""Constants used across memory-mcp."""

# Default values
DEFAULT_IMPORTANCE = 0.5
DEFAULT_EMOTION = "neutral"
DEFAULT_EMOTION_INTENSITY = 0.0
DEFAULT_PHYSICAL_STATE = "normal"
DEFAULT_MENTAL_STATE = "calm"
DEFAULT_ENVIRONMENT = "unknown"

# Search thresholds
SIMILARITY_THRESHOLD_HIGH = 0.80
SIMILARITY_THRESHOLD_MEDIUM = 0.60
SIMILARITY_THRESHOLD_LOW = 0.40

# Privacy levels
PRIVACY_LEVELS = ["public", "internal", "private", "secret"]
DEFAULT_PRIVACY_LEVEL = "internal"

# Vector store settings
DEFAULT_TOP_K = 5
DEFAULT_BATCH_SIZE = 100
MAX_CONTENT_LENGTH = 10000

# Time constants
SECONDS_PER_DAY = 86400
DAYS_PER_YEAR = 365
```

### 6. エラーハンドリングの改善（優先度: 低）

**問題**: 一部の関数で例外が過度に広範囲で捕捉されている

**提案**:
```python
# 【改善前】
try:
    # 大量のコード
    ...
except Exception as e:
    return f"Failed: {str(e)}"

# 【改善後】
try:
    # コード
    ...
except DatabaseError as e:
    log_operation("operation", success=False, error=str(e))
    raise MemoryDatabaseError(f"Database operation failed: {e}") from e
except ValidationError as e:
    log_operation("operation", success=False, error=str(e))
    raise MemoryValidationError(f"Invalid input: {e}") from e
except Exception as e:
    log_operation("operation", success=False, error=str(e))
    raise MemoryOperationError(f"Unexpected error: {e}") from e
```

カスタム例外クラスを定義:
```python
# core/exceptions.py
class MemoryMCPError(Exception):
    """Base exception for memory-mcp."""
    pass

class MemoryDatabaseError(MemoryMCPError):
    """Database operation errors."""
    pass

class MemoryValidationError(MemoryMCPError):
    """Input validation errors."""
    pass

class MemoryOperationError(MemoryMCPError):
    """General operation errors."""
    pass
```

---

## リファクタリング実施順序の推奨 🎯

1. **Phase 1: 即座に実施可能** ✅ (完了)
   - 重複インポートの削除
   - グローバル変数のクラス化

2. **Phase 2: 高優先度**
   - 長い関数の分割 (get_memory_stats, create_memory)
   - 統計データクラスの導入

3. **Phase 3: 中優先度**
   - 型ヒントの追加
   - 定数の集約

4. **Phase 4: 低優先度**
   - エラーハンドリングの改善
   - ドキュメントの拡充

---

## 測定指標 📊

### 改善前の状態
- **総行数**: 約10,000行
- **平均関数長**: 約50行
- **グローバル変数**: 12個（vector_utils.py）
- **型ヒント率**: 約40%

### 改善後の目標
- **平均関数長**: 30行以下
- **グローバル変数**: 0個（全てクラス化）
- **型ヒント率**: 90%以上
- **コード重複率**: 5%以下

---

## 参考リンク 📚

- [Python Code Smells](https://refactoring.guru/refactoring/smells)
- [Clean Code in Python](https://github.com/zedr/clean-code-python)
- [PEP 8 - Style Guide for Python Code](https://www.python.org/dev/peps/pep-0008/)

---

**作成日**: 2026年2月9日
**担当**: ニィロウ 🌸

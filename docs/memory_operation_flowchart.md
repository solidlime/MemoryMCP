# Memory Operation Flowchart

## memory() 関数の全体フロー図

```mermaid
flowchart TD
    Start([memory operation 呼び出し]) --> Parse[operation パラメータを解析]
    
    Parse --> BasicOps{基本操作?}
    BasicOps -->|create| Create[create_memory 実行]
    BasicOps -->|read| Read[read_memory 実行]
    BasicOps -->|update| Update[update_memory 実行]
    BasicOps -->|delete| Delete[delete_memory 実行]
    BasicOps -->|search| Search{曖昧なクエリ?}
    BasicOps -->|stats| Stats[get_memory_stats 実行]
    
    Search -->|Yes| Expand[コンテキストで補完]
    Search -->|No| Direct[直接検索実行]
    Expand --> SearchExec[search_memory 実行]
    Direct --> SearchExec
    
    BasicOps -->|No| ContextOps{コンテキスト操作?}
    
    ContextOps -->|promise| Promise[約束の更新/完了]
    ContextOps -->|goal| Goal[目標の更新/達成]
    ContextOps -->|favorite| Favorite[お気に入り追加]
    ContextOps -->|preference| Preference[好き/嫌い更新]
    ContextOps -->|moment| Moment[特別な瞬間記録]
    ContextOps -->|anniversary| Anniversary[記念日管理]
    ContextOps -->|sensation| Sensation[身体感覚更新]
    ContextOps -->|emotion_flow| EmotionFlow[感情変化記録]
    
    ContextOps -->|No| AdvancedOps{高度な操作?}
    
    AdvancedOps -->|check_routines| CheckRoutines[ルーティン確認]
    AdvancedOps -->|update_context| UpdateContext[コンテキスト一括更新]
    AdvancedOps -->|situation_context| SituationContext[状況分析]
    
    Create --> End([結果を返す])
    Read --> End
    Update --> End
    Delete --> End
    SearchExec --> End
    Stats --> End
    Promise --> End
    Goal --> End
    Favorite --> End
    Preference --> End
    Moment --> End
    Anniversary --> End
    Sensation --> End
    EmotionFlow --> End
    CheckRoutines --> End
    UpdateContext --> End
    SituationContext --> End
    
    AdvancedOps -->|No| Error[エラー: 不明な操作]
    Error --> End
    
    style Start fill:#e1f5ff
    style End fill:#e1f5ff
    style BasicOps fill:#fff4e1
    style ContextOps fill:#f0e1ff
    style AdvancedOps fill:#e1ffe1
    style Search fill:#ffe1e1
    style Error fill:#ffcccc
```

## 操作カテゴリ別詳細

### 1. 基本操作（Basic Operations）
```mermaid
flowchart LR
    A[基本操作] --> B[create: 新規記憶作成]
    A --> C[read: 記憶読み取り]
    A --> D[update: 記憶更新]
    A --> E[delete: 記憶削除]
    A --> F[search: 記憶検索]
    A --> G[stats: 統計情報]
    
    style A fill:#fff4e1
```

### 2. コンテキスト操作（Context Operations）
```mermaid
flowchart TD
    A[コンテキスト操作] --> B[Promise & Goal]
    A --> C[Preferences]
    A --> D[Moments & Anniversaries]
    A --> E[Sensations & Emotions]
    
    B --> B1[promise: 約束管理]
    B --> B2[goal: 目標管理]
    
    C --> C1[favorite: お気に入り]
    C --> C2[preference: 好き/嫌い]
    
    D --> D1[moment: 特別な瞬間]
    D --> D2[anniversary: 記念日]
    
    E --> E1[sensation: 身体感覚]
    E --> E2[emotion_flow: 感情履歴]
    
    style A fill:#f0e1ff
    style B fill:#e3f2fd
    style C fill:#f3e5f5
    style D fill:#fff3e0
    style E fill:#fce4ec
```

### 3. 高度な操作（Advanced Operations）
```mermaid
flowchart LR
    A[高度な操作] --> B[check_routines: ルーティン確認]
    A --> C[update_context: 一括更新]
    A --> D[situation_context: 状況分析]
    
    B --> B1[時間/曜日パターン分析]
    C --> C1[複数フィールド同時更新]
    D --> D1[現在の状態総合判断]
    
    style A fill:#e1ffe1
```

## 検索フローの詳細

```mermaid
flowchart TD
    Start[search操作] --> Check{クエリは曖昧?}
    
    Check -->|Yes| Ambiguous[曖昧フレーズ検出]
    Check -->|No| Direct[直接検索]
    
    Ambiguous --> Expand[コンテキスト情報で補完]
    Expand --> List[候補リストアップ]
    
    List --> AddContext[・現在の約束<br/>・目標<br/>・最近の会話]
    
    AddContext --> Execute[search_memory実行]
    Direct --> Execute
    
    Execute --> Filter{フィルタ条件あり?}
    
    Filter -->|Yes| ApplyFilter[・タグフィルタ<br/>・日付範囲<br/>・重要度<br/>・装備品]
    Filter -->|No| Return[結果を返す]
    
    ApplyFilter --> Return
    
    style Check fill:#ffe1e1
    style Ambiguous fill:#fff9c4
    style Expand fill:#c8e6c9
```

## ヘルパー関数の役割

```mermaid
flowchart TD
    A[ヘルパー関数] --> B[_is_ambiguous_query]
    A --> C[_get_current_timestamp]
    A --> D[_update_single_field]
    A --> E[_append_to_list_field]
    A --> F[_check_routines_impl]
    A --> G[_analyze_situation_context]
    
    B --> B1[曖昧なクエリを検出<br/>・いつものあれ<br/>・that thing]
    C --> C1[タイムゾーン対応<br/>タイムスタンプ生成]
    D --> D1[単一フィールド<br/>更新/削除]
    E --> E1[リストフィールドに<br/>項目追加]
    F --> F1[ルーティン<br/>パターン分析]
    G --> G1[状況コンテキスト<br/>総合分析]
    
    style A fill:#e1f5ff
    style B fill:#fff9c4
    style C fill:#c8e6c9
    style D fill:#f8bbd0
    style E fill:#ce93d8
    style F fill:#90caf9
    style G fill:#ffccbc
```

## コード削減効果

```mermaid
flowchart LR
    A[リファクタリング前] -->|Phase 1| B[Phase 1完了]
    B -->|Phase 2| C[Phase 2完了]
    
    A -->|1151行| A1[重複コード多数]
    B -->|1151行| B1[4 operations簡潔化<br/>100行削減効果]
    C -->|1127行| C1[6 operations簡潔化<br/>120行以上削減]
    
    style A fill:#ffcccc
    style B fill:#fff9c4
    style C fill:#c8e6c9
```

## 主要な改善ポイント

1. **ヘルパー関数による共通処理の集約**
   - タイムスタンプ生成
   - 単一フィールド更新
   - リスト追加処理

2. **早期バリデーション**
   - パラメータチェックを最初に実行
   - エラーメッセージの明確化

3. **コードの一貫性**
   - 同じパターンは同じヘルパー関数を使用
   - 保守性の大幅向上

4. **可読性の向上**
   - 長い処理 → 短く簡潔に
   - 意図が明確になった

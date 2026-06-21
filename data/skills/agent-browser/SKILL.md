---
name: agent-browser
description: agent-browser CLI を使ったWebブラウザ自動操作。検索、ページ遷移、フォーム入力、データ抽出、スクリーンショット。web_search ツールでDuckDuckGo検索も可能。
---

# agent-browser

ブラウザ自動化 CLI（Chrome/CDP、Playwright/Puppeteer非依存）。
アクセシビリティツリーのスナップショット + `@eN` リファレンスでページ操作を行います。

## コアループ

```
open <URL> → snapshot -i → act on @eN → snapshot -i → ...
```

`@eN` リファレンスはスナップショット毎に再割り当て。ページ変化（遷移・フォーム送信・動的再描画）後は必ず再スナップショット。

## 主要コマンド

| 操作 | コマンド |
|------|----------|
| ページを開く | `agent-browser open <URL>` |
| スナップショット（操作要素のみ） | `agent-browser snapshot -i` |
| フルスナップショット | `agent-browser snapshot` |
| JSONスナップショット | `agent-browser snapshot -i --json` |
| CSS選択子でスコープ | `agent-browser snapshot -s "#main"` |
| クリック | `agent-browser click @eN` |
| テキスト入力（全消去→入力） | `agent-browser fill @eN "text"` |
| 追加入力（消去なし） | `agent-browser type @eN "text"` |
| キー押下 | `agent-browser press Enter` / `press Control+a` |
| チェックボックス | `agent-browser check @eN` / `uncheck @eN` |
| セレクト | `agent-browser select @eN "value"` |
| ファイルアップロード | `agent-browser upload @eN file.pdf` |
| テキスト取得 | `agent-browser get text @eN` |
| HTML取得 | `agent-browser get html @eN` |
| 属性取得 | `agent-browser get attr @eN href` |
| 要素数カウント | `agent-browser get count ".selector"` |
| タイトル/URL取得 | `agent-browser get title` / `get url` |
| スクリーンショット | `agent-browser screenshot [path]` |
| フルページSS | `agent-browser screenshot --full` |
| アノテーション付きSS | `agent-browser screenshot --annotate` |
| スクロール | `agent-browser scroll down 500` |
| 要素表示までスクロール | `agent-browser scrollintoview @eN` |
| JavaScript評価 | `agent-browser eval "..."` または `eval --stdin` (ヒアドキュメント) |
| ブラウザを閉じる | `agent-browser close` / `close --all` |

## セマンティックロケーター（ref不要）

```
agent-browser find role button click --name "Submit"
agent-browser find text "Sign In" click
agent-browser find label "Email" fill "user@test.com"
agent-browser find placeholder "Search" type "query"
agent-browser find testid "submit-btn" click
agent-browser find first ".card" click
agent-browser find nth 2 ".card" hover
```

## 待機（最重要）

```bash
agent-browser wait @eN                     # 要素が現れるまで
agent-browser wait --text "Success"        # テキストが現れるまで
agent-browser wait --url "**/dashboard"    # URLがパターン一致するまで
agent-browser wait --load networkidle      # ネットワークアイドルまで
agent-browser wait 2000                    # 固定ミリ秒（最終手段）
```

## タブ管理

```bash
agent-browser tab                    # タブ一覧
agent-browser tab new <URL>          # 新規タブ
agent-browser tab 2                  # タブ2に切替
agent-browser tab close 2            # タブ2を閉じる
```

## セッション永続化

```bash
agent-browser state save ./auth.json   # 認証状態保存
agent-browser --state ./auth.json open <URL>  # 復元して開く
AGENT_BROWSER_SESSION_NAME=myapp agent-browser open <URL>  # 自動保存/復元
```

## 並列セッション

```bash
agent-browser --session a open <URL>
agent-browser --session b open <URL>
```

## ネットワークモック

```bash
agent-browser network route "**/api/users" --body '{"users":[]}'
agent-browser network route "**/analytics" --abort
agent-browser network requests    # リクエスト一覧
```

## トラブルシューティング

- **"Ref not found"**: ページが変わった。再スナップショット。
- **要素がスナップショットにない**: オフスクリーンか未レンダリング。`scroll down` → `wait --text`。
- **クリックが効かない**: モーダル/クッキーバナーがブロック。先に閉じる。
- **fill/type が効かない**: `focus @eN` → `keyboard inserttext "text"` を試す。
- **複雑なJS**: 必ず `eval --stdin` + ヒアドキュメントで。インライン `eval "..."` はクォート問題が起きやすい。

## 利用可能なツール

- **`web_search`**: DuckDuckGoでWeb検索。結果はタイトル・URL・スニペットの配列。
- **`sandbox_files`**: サンドボックス内のファイル操作（読込・書込・一覧・削除）。
- **`sandbox_execute`**: サンドボックス内で Python/Bash コード実行。

## グローバルフラグ

`--headed`（ウィンドウ表示）、`--json`（JSON出力）、`--profile <name>`（Chromeプロファイル）、`--proxy <url>`、`--headers <json>`

---
name: search
description: SearXNG 検索エンジンを使った Web 検索。最新情報の検索、事実確認、ドキュメント検索に search ツールを使用する。Google/Bing/DuckDuckGo 等の主要検索エンジンを透過的に利用可能。
license: MIT
compatibility: memory-mcp >= 2.0.0
---

# 検索スキル

`search` ツールを使ってインターネット検索を行います。
このツールは SearXNG メタサーチエンジンを経由し、Google、Bing、DuckDuckGo 等の
主要検索エンジンの結果を集約して返します。

## 使い方

- 最新情報や事実確認が必要な時に `search(query="...")` を呼び出す
- 結果には title, url, content（スニペット）が含まれる
- 必要に応じて `browser` ツールで結果の URL を開き詳細を取得できる

## 注意

- 検索結果は要約してユーザーに伝えること
- 情報源の URL を適切に引用すること
- `browser` ツールと組み合わせて使うとより深い情報が得られる

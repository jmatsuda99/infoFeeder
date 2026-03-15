# Google Alerts RSS Viewer

Google Alerts の RSS を登録・取得・一覧表示する Streamlit アプリです。

## できること

- RSS URLを後から追加
- フィードの有効/無効切替
- フィード削除
- 有効フィードをまとめて取得
- 記事一覧の検索
- 複数記事の詳細表示
- 同一記事の重複除去
  - 保存時にURLのquery/fragmentを除去
  - 表示時に `link` 単位で集約
- 旧版 `feeds` テーブルが残っていても起動時に自動移行
- GitHub Actionsで30分ごとにRSS取得

## セットアップ

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 既存DBについて

過去に `?utm_...` 付きURLが保存済みの場合は、よりきれいに重複を消したいときに
`data/alerts.db` を削除して再取得してください。

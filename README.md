# Google Alerts RSS Viewer

Google Alerts や RSS/Atom フィードをまとめて取得し、Streamlit 上で記事一覧を確認するツールです。

## 主な機能

- Google Alerts RSS URL の一括登録
- RSS/Atom と HTML listing の自動判別
- 未読 / 既読 / すべて の表示切り替え
- 記事一覧の並び順切り替え
- `新しい順`
- `古い順`
- `保存記事を先頭`
- 保存済み記事の管理
- 30分ごとの自動更新

## 起動方法

リポジトリ直下の `.venv` を使います。

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502
```

バックグラウンド起動を使う場合は、以下のどちらかを実行します。

- `start_infofeeder.bat`
- `start_infofeeder.vbs`

起動後は `http://localhost:8502` を開いて確認します。

## メモ

- ソース設定タブで RSS URL やベース URL を追加できます。
- 記事一覧タブでキーワード検索、件数変更、既読管理、保存管理ができます。
- 次回の自動取得時刻は画面上部に表示されます。

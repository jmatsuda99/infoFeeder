# Google Alerts RSS Viewer

Google Alerts の RSS/Atom フィードを収集し、Streamlit 上で一覧確認・整理できるツールです。

## 主な機能

- Google Alerts RSS URL の一括登録
- ベース URL から RSS/Atom または HTML listing の自動判定
- 記事の未読 / 既読 / 保存管理
- 記事一覧のキーワード検索、件数制限、並び替え
- 保存済み記事のみの絞り込み
- 表示中の記事一覧を CSV 出力
- 00分 / 30分の自動取得
- 除外ドメイン設定

## 画面構成

### ソース設定

- フィード追加
- Google Alerts RSS の一括登録
- 除外ドメイン設定
- 登録済みソースの管理

`除外ドメイン設定` はソース設定タブの上側に表示されます。  
登録済みソース一覧までスクロールしなくても設定できます。

### 記事一覧

- キーワード検索
- 未読 / 既読 / すべて の切り替え
- 保存済み記事のみの絞り込み
- 既読 / 保存操作
- 詳細表示
- CSV 出力

## 主なファイル

- [app.py](./app.py)
  - アプリの入口。タブ表示と自動取得の配線を担当します。
- [ui_common.py](./ui_common.py)
  - 共通 UI、日時表示、リロード制御をまとめています。
- [summary_view.py](./summary_view.py)
  - サマリーカード表示を担当します。
- [source_setup_view.py](./source_setup_view.py)
  - ソース設定画面を担当します。
- [articles_view.py](./articles_view.py)
  - 記事一覧画面を担当します。
- [db.py](./db.py)
  - SQLite まわりの処理をまとめています。
- [fetcher.py](./fetcher.py)
  - フィード取得とソース判定を担当します。

## 起動方法

リポジトリ直下の `.venv` を使います。

```powershell
.\.venv\Scripts\python.exe launcher.py open
```

このコマンドは以下をまとめて行います。

- Streamlit アプリの起動
- `http://localhost:8502` の待ち受け確認
- ブラウザでアプリを開く

ブラウザを開かずに直接起動したい場合は、次でも起動できます。

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502 --server.headless true
```

## 自動取得

- ブラウザでアプリを開いたままにしておくと、毎時 `00` 分と `30` 分に自動取得します。
- 自動取得は対象時刻にページを再読み込みし、その時間枠で一度だけ実行されます。
- `次回取得` は次の自動取得予定時刻を表示します。

## CSV 出力

記事一覧画面の `CSV出力` ボタンから、現在の表示条件に一致する記事をダウンロードできます。

出力列:

- `title`
- `link`
- `source`
- `category`
- `published_jst`
- `is_read`
- `is_saved`
- `summary`

## Windows での補助起動

- [start_infofeeder.bat](./start_infofeeder.bat)
  - コンソール表示ありで起動します。
- [start_infofeeder.vbs](./start_infofeeder.vbs)
  - コンソールを出さずに起動します。
- `Google Alerts RSS Viewer.lnk`
  - 起動用ショートカットです。

## Versioning

- バージョンは [VERSION](./VERSION) を正本として管理しています。
- 表示用の値は [version.py](./version.py) から読み込みます。
- コミットメッセージに応じた更新は `.githooks/commit-msg` と補助スクリプトで行います。
- 利用者向け機能追加だけでなく、不具合修正もバージョン更新対象です。

## 開発メモ

- SQLite は `WAL` と `busy_timeout` を利用しています。
- 自動取得の排他には `data/fetch.lock` を使っています。
- 依存追加は原則として事前確認を前提にしています。

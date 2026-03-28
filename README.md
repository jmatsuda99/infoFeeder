## Windows Commit Flow

- Windows では Git hook による自動バージョン更新が環境依存で失敗することがあります。
- そのため、このリポジトリでは `commit_with_version.bat` をコミット入口として使う運用を追加しました。
- `commit_with_version.py` がコミットメッセージから更新種別を判定し、`VERSION` を更新してから `git commit` を実行します。
- `feat:` は minor、`fix:` `refactor:` `docs:` `test:` `chore:` `perf:` `style:` は patch、`feat!:` や `BREAKING CHANGE` は major です。
- 使い方:

```powershell
.\commit_with_version.bat "feat: add exclusion settings"
```

- コミットが失敗した場合は `VERSION` を元に戻します。

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
- 記事一覧フィルタの保持

## 起動方法

リポジトリ直下の `.venv` を使います。

前面起動:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502 --server.headless true
```

起動後は `http://localhost:8502` を開いて確認します。

## ダブルクリック起動

- `start_infofeeder.bat`
  - 手動起動用です。コンソール付きで起動します。
- `start_infofeeder.vbs`
  - 非表示起動用です。エクスプローラーからダブルクリックできます。
- `Google Alerts RSS Viewer.lnk`
  - ショートカットです。ダブルクリック起動用に使えます。

## 安定化メモ

- SQLite は `WAL` と `busy_timeout` を使うようにしています。
- 書き込み系処理は `database is locked` 時にリトライします。
- 自動取得は `data/fetch.lock` で排他し、複数セッションの同時取得を避けています。
- `init_db()` の補完更新は必要なときだけ実行します。

## メモ

- ソース設定タブで RSS URL やベース URL を追加できます。
- 記事一覧タブでキーワード検索、件数変更、既読管理、保存管理ができます。
- 次回の自動取得時刻は画面上部に表示されます。
## Versioning

- 表示バージョンは `VERSION` ファイルを正本として管理します。
- `app.py` は `version.py` 経由でその値を表示します。
- コミット時は `.githooks/commit-msg` が `VERSION` を自動更新します。
- 判定ルールはコミットメッセージ先頭です。
- `feat:` は `Y` を上げます。
- `fix:` `refactor:` `docs:` `test:` `chore:` `perf:` は `Z` を上げます。
- `feat!:` などの `!` 付き、または本文に `BREAKING CHANGE` を含む場合は `X` を上げます。
- 例: `fix: adjust article rendering`、`feat: add exclusion settings`
## Startup Update

- 起動入口は `launcher.py` に一本化しました。
- `launcher.py` は `.venv` の確認、Streamlit のバックグラウンド起動、`http://localhost:8502` の待受確認、ブラウザ起動をまとめて担当します。
- `start_infofeeder.bat` は `python launcher.py open` を呼ぶだけの薄い入口です。
- `start_infofeeder.vbs` はその `bat` を非表示で起動するだけです。
- 普段の起動はデスクトップのショートカット、または `start_infofeeder.bat` を使えば十分です。
- 手元で直接確認したいときは次のコマンドでも起動できます。

```powershell
.\.venv\Scripts\python.exe launcher.py open
```

# Google Alerts RSS Viewer

Google Alerts の RSS を登録・取得・一覧表示する Streamlit アプリです。

## できること

- RSS URLを後から追加
- フィードの有効/無効切替
- フィード削除
- 有効フィードをまとめて取得
- 記事一覧の検索
- 複数記事の詳細表示
- 旧版 `feeds` テーブルが残っていても起動時に自動移行
- GitHub Actionsで30分ごとにRSS取得

## セットアップ

```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub Actions

`.github/workflows/fetch_rss.yml` により、毎時7分・37分に `run_fetch.py` が実行されます。

### 初回に必要なこと

1. このリポジトリを GitHub に push
2. GitHub の Actions を有効化
3. アプリ上で RSS URL を登録
4. `workflow_dispatch` か定期実行で `data/alerts.db` を更新

## 注意

- `data/alerts.db` は GitHub Actions から更新して commit/push する前提なので、`.gitignore` から除外していません。
- GitHub Actions の `schedule` は高負荷時に遅れることがあります。

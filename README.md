
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

## セットアップ

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud での注意

旧DBスキーマが残っていても `init_db()` 内で `feeds` テーブルを新しい構成へ移行します。

# Google Alerts RSS Viewer

Google Alerts の RSS URL を後から追加・編集しながら管理できる Streamlit アプリです。

## 主な機能

- RSS URL の追加
- RSS URL の編集
- 有効 / 無効の切り替え
- フィード削除
- 有効フィードの一括取得
- 記事一覧の検索 / 絞り込み
- SQLite でのローカル保存

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate   # Windows は .venv\\Scripts\\activate
pip install -r requirements.txt
```

## 起動

```bash
streamlit run app.py
```

## GitHub へアップロード

```bash
git init
git add .
git commit -m "Initial commit: Google Alerts RSS Viewer"
git branch -M main
git remote add origin <YOUR_REPO_URL>
git push -u origin main
```

## 補足

- `data/alerts.db` は実行時に自動生成されます。
- `.gitignore` でDBとキャッシュは除外しています。

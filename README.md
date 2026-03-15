# Google Alerts RSS Viewer (feeds.json 共有版)

定期取得で新規記事が入らない問題を避けるため、RSS設定を `feeds.json` に分離した版です。

## 重要

- Streamlit アプリも GitHub Actions も **同じ `feeds.json`** を参照します。
- 定期取得に反映させるには、`feeds.json` を GitHub リポジトリに commit してください。
- アプリ上で `feeds.json` を更新しても、ホスティング環境によっては永続化されないことがあります。

## セットアップ

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 30分ごとの定期取得

`.github/workflows/fetch_rss.yml` により、毎時 7 分 / 37 分に `run_fetch.py` が実行されます。

## まずやること

1. `feeds.json` を自分の RSS URL に書き換える
2. GitHub に push する
3. Actions を有効化する
4. 必要なら Streamlit 側でも同じリポジトリを再デプロイする

## 重複除去

- 保存時に URL の query / fragment を除去
- 表示時に `link` 単位で集約

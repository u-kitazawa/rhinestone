# 07 — 検索して取得する

G空間情報センターのCKANカタログを検索し、検索結果の一つを通常の解決フローへ渡すlive exampleです。

## 準備と実行

```console
cd rhinestone
uv sync --dev
export RHINESTONE_QUERY="人口"
uv run python examples/07_search_and_fetch/example.py
```

接続先は`rhinestone.sources.GEOSPATIAL_JP`に定義され、HTTP通信は組み込みtransportを使います。

結果は提供元の状態で変わるため、CIで固定的に確認する例ではありません。検索結果を選んでも、
Configの検証と通常の解決処理は省略されません。

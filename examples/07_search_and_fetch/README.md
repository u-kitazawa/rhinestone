# 07 — 検索結果のResourceを確認する

G空間情報センターのカタログを検索し、取得した`Resource`のURI・メタデータ・出典情報を表示するlive exampleです。
選択した結果を`app.load()`で再解決したり、`open()`でデータ本体を開いたりはしません。

## 準備と実行

```console
cd rhinestone
uv sync --dev
export RHINESTONE_QUERY="人口"
uv run python examples/07_search_and_fetch/example.py
```

接続先は`BUILTIN`内の`geospatial-jp` Providerに定義され、HTTP通信は組み込みtransportを使います。

結果は提供元の状態で変わり、検索結果が1件以上あることを前提とします。
実サービスの検索品質・可用性は通常CIのfixtureテストでは保証しません。

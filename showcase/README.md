# Rhinestone Showcase

`showcase/` は、Rhinestone の価値を実行結果とともに伝える Notebook を置く場所です。
短い使い方は [`examples/`](../examples/README.md)、手順中心の解説は
[`docs/tutorials/`](../docs/tutorials/index.md) を参照してください。

## 01 — CKAN を検索して地図に表示する

[GitHub で Notebook を読む](01_ckan_search_to_map.ipynb) ·
[Colab で開く](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/01_ckan_search_to_map.ipynb)

G空間情報センターの公開 CKAN を検索し、利用者が選んだ GeoJSON 配布物を
Rhinestone で解決してから、利用者所有の `pyogrio` / GeoPandas で GeoJSON を開き、
Folium の操作できるベクターレイヤーとして地理院タイル上に表示します。選択したデータの
範囲へ自動で移動するため、検索結果が何を表すかを地図で確認できます。

```text
configure -> search -> Result を選ぶ -> resolve -> Resource -> AccessPlan
    -> pyogrio -> GeoDataFrame -> Folium map
```

この Notebook は live Provider を利用します。検索結果、配布 URL、公開状態は提供元によって
変わるため、通常 CI での完全実行は要求しません。検索結果に GeoJSON 候補がないときは、
URL・形式・archive 内部を推測せず、明示的に停止します。

Rhinestone の責務は、CKAN 検索、選択した配布物の解決、`Resource` と `AccessPlan` の決定、
および登録済み Runtime への委譲までです。GeoDataFrame の表示、地理院タイルの取得、
操作できる地図レイヤー、解析、形式変換は pyogrio、GeoPandas、Folium など downstream
library の責務です。背景タイルは追加のネットワーク接続と
[地理院タイルの利用条件](https://maps.gsi.go.jp/development/ichiran.html#std)に従います。

Notebook の setup は Rhinestone Core の依存関係を変更しません。secret や credential は不要で、
Notebook の保存済み出力にも含めません。

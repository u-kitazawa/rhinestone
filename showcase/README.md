# Rhinestone Showcase

`showcase/` は、Rhinestone の主要フローを実行済みの Jupyter Notebook として確認するための入口です。
各 Notebook は上から順に実行でき、保存された出力から `Result`、`Resource`、`AccessPlan` を
確認できます。短い使い方は [`examples/`](../examples/README.md)、手順中心の解説は
[`docs/tutorials/`](../docs/tutorials/index.md) を参照してください。

## Notebook

| Notebook | 内容 | 外部通信 | 追加 Runtime |
| --- | --- | --- | --- |
| [01 Search and Resource](01_search_and_resource.ipynb) | 組み込み GSI 定義を検索し、`Result` を `Resource` へ解決して来歴と AccessPlan を確認 | 不要 | 不要 |
| [02 CKAN Search to Map](02_ckan_search_to_map.ipynb) · [Colab](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/codex/showcase-interactive-map/showcase/02_ckan_search_to_map.ipynb) | 公開 CKAN から GeoJSON を解決し、操作できる Folium ベクターレイヤーとして地理院タイル上に表示 | 必要 | pyogrio、GeoPandas、Folium |

各 Notebook の Colab リンクから、そのまま Google Colab で開けます。ローカルでは
リポジトリの開発環境を準備して Jupyter 互換環境から開いてください。Colab だけは Notebook 内の
setup cell が公開パッケージを導入します。

## 02 — CKAN を検索して地図に表示する

[GitHub で Notebook を読む](02_ckan_search_to_map.ipynb) ·
[Colab で開く](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/codex/showcase-interactive-map/showcase/02_ckan_search_to_map.ipynb)

G 空間情報センターの公開 CKAN を検索し、明示的に GeoJSON と広告された配布物を Rhinestone で解決してから、
利用者所有の pyogrio / GeoPandas で GeoJSON を開き、Folium の操作できるベクターレイヤーとして
地理院タイル上に表示します。選択したデータの範囲へ自動で移動するため、検索結果が何を表すかを
地図で確認できます。

```text
configure -> search -> GeoJSON Result -> resolve -> Resource -> AccessPlan
    -> pyogrio -> GeoDataFrame -> Folium map
```

この Notebook は live Provider を利用します。検索結果、配布 URL、公開状態は提供元によって変わるため、
通常 CI での完全実行は要求しません。検索結果に GeoJSON 候補がないときは、URL・形式・archive 内部を
推測せず、明示的に停止します。

## 再現性と境界

- `01_search_and_resource.ipynb` は、組み込みの静的 GSI 定義だけを使います。外部サービスの状態、
  API key、ネットワークに依存せず、通常 CI でコードセルを再実行できます。
- 検索結果の並びは Provider の構成順と各 Provider 内の順序です。Provider をまたぐ関連度ランキング
  ではありません。
- `uri` は外部データの所在地を示しますが、最初の Notebook はデータ本体を取得せず、`open()` も実行しません。
- CKAN Notebook では、Rhinestone は検索、選択した配布物の解決、`Resource` と `AccessPlan` の決定、
  および登録済み Runtime への委譲までを担います。表示、地理院タイルの取得、操作できる地図レイヤー、
  解析、形式変換は pyogrio、GeoPandas、Folium など downstream library の責務です。背景タイルは追加の
  ネットワーク接続と[地理院タイルの利用条件](https://maps.gsi.go.jp/development/ichiran.html#std)に従います。
- 保存出力には秘密情報や大きなデータを含めません。Notebook の構文、metadata、再実行結果、出力サイズは
  テストで検証します。ライブ Provider への疎通は通常 CI の必須条件にしません。

## データと利用条件

最初の Notebook は国土地理院の組み込みメタデータを利用します。解決結果に含まれる
`metadata.raw["usage_url"]` と `usage_notes` を確認し、実データ利用時は提供元の最新条件に従ってください。
CKAN Notebook の公開データと地理院タイルにも各提供元の利用条件が適用されます。Notebook のコード自体は
リポジトリと同じ MIT License です。

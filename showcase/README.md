# Rhinestone Showcase

`showcase/` は、Rhinestone の主要フローを実行済みの Jupyter Notebook として確認するための入口です。
各 Notebook は上から順に実行でき、保存された出力から `Result`、`Resource`、`AccessPlan` を
確認できます。短い使い方は [`examples/`](../examples/README.md)、手順中心の解説は
[`docs/tutorials/`](../docs/tutorials/index.md) を参照してください。

## Notebook

| Notebook | 内容 | 外部通信 | 追加 Runtime |
| --- | --- | --- | --- |
| [01 Search and Resource](01_search_and_resource.ipynb) | 組み込み GSI 定義を検索し、`Result` を `Resource` へ解決して来歴と AccessPlan を確認 | 不要 | 不要 |
| [02 CKAN Search to Map](02_ckan_search_to_map.ipynb) · [Colab](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/02_ckan_search_to_map.ipynb) | 公開 CKAN から明示的なベクター配布物（ZIP Shapefile を含む）を解決し、操作できる Folium ベクターレイヤーとして地理院タイル上に表示 | 必要 | pyogrio、GeoPandas、Folium |
| [03 STAC COG Preview](03_stac_cog_preview.ipynb) · [Colab](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/03_stac_cog_preview.ipynb) | 明示した STAC Item / asset を COG Resource へ解決し、Rasterio で縮小プレビューを表示 | 必要 | Rasterio、Matplotlib |

各 Notebook の Colab リンクから、そのまま Google Colab で開けます。ローカルでは
リポジトリの開発環境を準備して Jupyter 互換環境から開いてください。Colab だけは Notebook 内の
setup cell が公開パッケージを導入します。

## 02 — CKAN を検索して地図に表示する

[GitHub で Notebook を読む](02_ckan_search_to_map.ipynb) ·
[Colab で開く](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/02_ckan_search_to_map.ipynb)

G 空間情報センターの公開 CKAN を検索し、明示的に広告されたベクター配布物（ZIP Shapefile を含む）を Rhinestone で解決してから、
利用者所有の pyogrio / GeoPandas で開き、Folium の操作できるベクターレイヤーとして
地理院タイル上に表示します。選択したデータの範囲へ自動で移動するため、検索結果が何を表すかを
地図で確認できます。

```text
configure(pyogrio) -> search -> resolve -> vector Resource -> AccessPlan
    -> open -> GeoDataFrame -> Folium map
```

この Notebook は live Provider を利用します。検索結果、配布 URL、公開状態は提供元によって変わるため、
通常 CI での完全実行は要求しません。検索結果に明示的なベクター候補がないときは、URL・形式・archive memberを
推測せず、明示的に停止します。ZIP を開く場合は、確定済みの `archive` と任意の `entry_point` を pyogrio 用の
GDAL VSI URI に翻訳します。

## 03 — STAC の COG を縮小表示する

[GitHub で Notebook を読む](03_stac_cog_preview.ipynb) ·
[Colab で開く](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/03_stac_cog_preview.ipynb)

利用する公開 STAC API、collection、Item、asset key を明示し、Rhinestone で COG Resource と
AccessPlan を解決します。選択済み URI は利用者所有の Rasterio Runtime へ渡し、画像全体を
原寸で取得せず、最大 512 × 512 の縮小データだけを読み込んで Matplotlib で表示します。

```text
configure(rasterio) -> explicit STAC Item / asset -> resolve -> COG Resource
    -> AccessPlan -> open -> Rasterio dataset -> bounded preview
```

Item、asset URL、media type は Provider 側で変わり得ます。Notebook は URL suffix や先頭 asset を
推測せず、4つの入力が不足している場合や、指定 asset が COG として広告されていない場合は停止します。

## 再現性と境界

- `01_search_and_resource.ipynb` は、組み込みの静的 GSI 定義だけを使います。外部サービスの状態、
  API key、ネットワークに依存せず、通常 CI でコードセルを再実行できます。
- 検索結果の並びは Provider の構成順と各 Provider 内の順序です。Provider をまたぐ関連度ランキング
  ではありません。
- `uri` は外部データの所在地を示しますが、最初の Notebook はデータ本体を取得せず、`open()` も実行しません。
- CKAN Notebook では、Rhinestone は検索、選択した配布物の解決、`Resource` と `AccessPlan` の決定、
  および登録済み Runtime への委譲までを担います。明示済み ZIP AccessPlan は VSI URI に翻訳します。表示、地理院タイルの取得、操作できる地図レイヤー、
  解析、形式変換は pyogrio、GeoPandas、Folium など downstream library の責務です。背景タイルは追加の
  ネットワーク接続と[地理院タイルの利用条件](https://maps.gsi.go.jp/development/ichiran.html#std)に従います。
- STAC Notebook では、Rhinestone は明示された Item / asset の検証、COG Resource と AccessPlan の決定、
  Rasterio への委譲までを担います。画像読込、縮小、band 選択、可視化は Rasterio / Matplotlib の責務です。
  公開 STAC の値は固定せず、利用する catalog で確認した値を環境変数または入力セルへ設定します。
- 保存出力には秘密情報や大きなデータを含めません。Notebook の構文、metadata、再実行結果、出力サイズは
  テストで検証します。ライブ Provider への疎通は通常 CI の必須条件にしません。

## データと利用条件

最初の Notebook は国土地理院の組み込みメタデータを利用します。解決結果に含まれる
`metadata.raw["usage_url"]` と `usage_notes` を確認し、実データ利用時は提供元の最新条件に従ってください。
CKAN Notebook の公開データと地理院タイルにも各提供元の利用条件が適用されます。Notebook のコード自体は
リポジトリと同じ MIT License です。

# Rhinestone Showcase

`showcase/` は、Rhinestone の主要フローを Jupyter Notebook で確認するための入口です。
まずは **05 → 06** で、国内の公園データの検索・地図表示と、別NotebookへのAccessPlan転送を試してください。
この2本には実Providerで検証した保存出力があります。実セルを別々のPythonプロセスで実行し、JSONだけを転送した結果です。
Jupyter kernel起動は検証環境の通信権限制約で失敗したため、Colab/Jupyter上の通し実行は未確認です。
検索・配信状態は変化するため、保存出力は将来の成功保証ではありません。
ラスターの初期設定不要化は[#211](https://github.com/u-kitazawa/rhinestone/issues/211)の残件であり、
この追加だけで[#212](https://github.com/u-kitazawa/rhinestone/issues/212)全体の完了とは扱いません。
01は実行済みの保存出力から`Resource`と`AccessPlan`を確認できます。
02〜04はlive Providerを利用するため保存出力を空にしてあり、入力・依存を準備して上から順に実行します。
短い使い方は [`examples/`](../examples/README.md)、手順中心の解説は
[`docs/tutorials/`](../docs/tutorials/index.md) を参照してください。

## Notebook

| Notebook | 内容 | 外部通信 | 追加 Runtime |
| --- | --- | --- | --- |
| [05 Vector Discover / Open](05_vector_discover_open.ipynb) · [Colab](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/05_vector_discover_open.ipynb) | search.ckan.jpで候補一覧→URI明示選択→実公園10地点の地図→Plan JSONの書出し | 必要 | pyogrio、GeoPandas、Matplotlib |
| [06 Portable Vector](06_portable_vector.ipynb) · [Colab](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/06_portable_vector.ipynb) | 05のJSONをアップロードし、検索元Providerなしで同じデータをOpen・表示 | 配布URLのみ | pyogrio、GeoPandas、Matplotlib |
| [01 Search and Resource](01_search_and_resource.ipynb) | 組み込み GSI 定義を検索し、`Resource`の来歴とAccessPlanを確認 | 不要 | 不要 |
| [02 CKAN Search to Map](02_ckan_search_to_map.ipynb) · [Colab](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/02_ckan_search_to_map.ipynb) | 公開 CKAN から明示的なベクター配布物（ZIP Shapefile を含む）を解決し、操作できる Folium ベクターレイヤーとして地理院タイル上に表示 | 必要 | pyogrio、GeoPandas、Folium |
| [03 STAC COG Preview](03_stac_cog_preview.ipynb) · [Colab](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/03_stac_cog_preview.ipynb) | 明示した STAC Item / asset を COG Resource へ解決し、Rasterio で縮小プレビューを表示 | 必要 | Rasterio、Matplotlib |
| [04 Discovery Lineage](04_discovery_lineage.ipynb) · [Colab](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/04_discovery_lineage.ipynb) | search.ckan.jp の発見 record と `direct` target の解決 record を分離して確認 | 必要 | 不要 |

各 Notebook の Colab リンクから、そのまま Google Colab で開けます。ローカルでは
リポジトリの開発環境を準備して Jupyter 互換環境から開いてください。Notebook内の
setup cellが固定コミットのRhinestoneと、必要に応じて固定バージョンの追加Runtimeを導入します。

## 05 → 06 — Discover / Open / Portable

05の入力はKEYWORDとSELECTED_URIの2箇所です。既定の公園GeoJSONは2026-10-20に
7,243 bytes・10地点・EPSG:4979を確認しました。検索はmetadata、Openは実ファイル取得です。
先頭結果の暗黙選択や別候補への自動フォールバックはしません。0件とProvider診断を区別し、
選択先がなければ一覧を確認するよう案内します。結果を変更する場合、容量・利用条件・表示に必要な列も確認してください。
`limit=3`は結果数の上限であり、検索APIの総要求回数・Openの転送量上限ではありません。

05で作成した`vector-plan.json`をダウンロードし、06の作業ディレクトリへアップロードします。
既存ファイルは上書きしません。06は新しいkernelで実行し、元の検索結果・Provider設定・変数を共有しません。
受信側には既知の配布URIだけをdirect Providerで許可します。JSON中の未知URIをそのまま許可しません。
Planはデータ本体・Runtime・Credentialを運ばず、配布URLの再読込みは発生します。
配布物の更新後まで同じ結果となるsnapshotではありません。

出典は那須塩原市 建設部 保全管理課「公園 都市整備施設」。
[元リソース](https://opendata-nasu.opendatastack.jp/dataset/shisetu-kouenn-tosisetibi/resource/d94a1299-e0fb-4c9a-9a9f-aac7dcb97763)と
[利用規約](https://opendata-nasu.opendatastack.jp/pages/userpolicy)を確認し、
[CC BY 2.1 JP](https://creativecommons.org/licenses/by/2.1/jp/)と出典・加工内容を各Notebookに表示します。
名称・位置だけを抽出して表示用CRSへ変換し、写真や外部画像・背景タイルは取得しません。
提供元の最終更新表示は2016-04-04です。現在の施設一覧・営業状況・測量精度は保証しません。

通常CIではNotebookのセルをfixtureで検証し、live Providerとnative Runtimeの可用性を必須にしません。
保守者のlocal smokeに限り`RHINESTONE_SHOWCASE_LOCAL=1`でsetupの再installを省略できます。
その場合はNotebookのpinと同じAPIを持つcheckoutと、明記した依存バージョンを別途準備し、検証commitを記録してください。
CAが環境依存の場合は、管理済みの信頼済みCAをGDALへ設定し、TLS検証を無効化しないでください。

## 02 — CKAN を検索して地図に表示する

[GitHub で Notebook を読む](02_ckan_search_to_map.ipynb) ·
[Colab で開く](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/02_ckan_search_to_map.ipynb)

G 空間情報センターの公開 CKAN を検索し、明示的に広告されたベクター配布物（ZIP Shapefile を含む）を Rhinestone で解決してから、
利用者所有の pyogrio / GeoPandas で開き、Folium の操作できるベクターレイヤーとして
地理院タイル上に表示します。選択したデータの範囲へ自動で移動するため、検索結果が何を表すかを
地図で確認できます。`providers=[ProviderId.GEOSPATIAL_JP]` で検索前に提供元を限定するため、
Notebookで `Reference` や `configure()` を組み立てる必要はありません。他のProviderへの検索・通信は行いません。

```text
search(format=PYOGRIO) -> Resource -> open(runtime=pyogrio)
    -> GeoDataFrame -> Folium map
```

この Notebook は live Provider を利用します。検索結果、配布 URL、公開状態は提供元によって変わるため、
通常 CI での完全実行は要求しません。検索結果の一覧から番号を指定し、解決後の形式・URL・AccessPlanを
確認してからベクターデータを開きます。検索例では `text="国土数値 ダム"` の複数語と `area="津市"` の市名指定を組み合わせ、
結果一覧にDatasetの対象地域を表示します。市の候補が不足すると県・地方・全国へ検索を広げるため、
各候補の対象地域を確認してください。ファイル内の地物の切り出しは行いません。
対象形式は検索時に `FormatPreset.PYOGRIO` で絞ります。
URL・形式・archive memberは推測しません。ZIP を開く場合は、確定済みの `archive` と任意の `entry_point` を pyogrio 用の
GDAL VSI URI に翻訳します。

## 03 — STAC の COG を縮小表示する

[GitHub で Notebook を読む](03_stac_cog_preview.ipynb) ·
[Colab で開く](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/03_stac_cog_preview.ipynb)

利用する公開 STAC API、collection、Item、asset key を明示し、Rhinestone で COG Resource と
AccessPlan を解決します。選択済み URI は利用者所有の Rasterio Runtime へ渡し、画像全体を
原寸で取得せず、最大 512 × 512 の縮小データだけを読み込んで Matplotlib で表示します。

```text
configure() -> explicit STAC Item / asset -> load -> COG Resource
    -> AccessPlan -> open -> Rasterio dataset -> bounded preview
```

Item、asset URL、media type は Provider 側で変わり得ます。Notebook は URL suffix や先頭 asset を
推測せず、4つの入力が不足している場合や、指定 asset が COG として広告されていない場合は停止します。

## 04 — Discovery source と resolution target

[GitHub で Notebook を読む](04_discovery_lineage.ipynb) ·
[Colab で開く](https://colab.research.google.com/github/u-kitazawa/rhinestone/blob/develop/showcase/04_discovery_lineage.ipynb)

search.ckan.jp の横断検索で得た `Resource` が、発見元とは異なる `direct` target へ解決される流れを示します。
発見側と解決側の metadata / provenance / raw record を flat merge せず、`Resource.discovery` と
`Resource` 本体へ分離して保持することを確認します。データ本体は開きません。

```text
search.ckan.jp -> Resource(discovered_by=search-ckan-jp)
    -> Reference(provider_id=direct) -> Resource + DiscoveryRecord
```

この Notebook は live Provider を利用します。検索結果が変化して cross-source result が得られない場合は、
URLや識別子を推測せず明示的に停止します。通常 CI では構文、契約marker、秘密情報非混入、空の実行出力を検査します。

## 再現性と境界

- `01_search_and_resource.ipynb` は、組み込みの静的 GSI 定義だけを使います。外部サービスの状態、
  API key、ネットワークに依存せず、通常 CI でコードセルを再実行できます。
- 検索結果の並びは Provider の構成順と各 Provider 内の順序です。Provider をまたぐ関連度ランキング
  ではありません。
- `uri` は外部データの所在地を示しますが、最初の Notebook はデータ本体を取得せず、`open()` も実行しません。
- CKAN Notebook では、Rhinestone は検索、選択した配布物の解決、`Resource` と `AccessPlan` の決定、
  およびopen時に渡したRuntimeへの委譲までを担います。明示済み ZIP AccessPlan は VSI URI に翻訳します。表示、地理院タイルの取得、操作できる地図レイヤー、
  解析、形式変換は pyogrio、GeoPandas、Folium など downstream library の責務です。背景タイルは追加の
  ネットワーク接続と[地理院タイルの利用条件](https://maps.gsi.go.jp/development/ichiran.html#std)に従います。
- Discovery lineage Notebook では、Rhinestone は発見側 record を `Resource.discovery`、解決側 record を `Resource` 本体として分離して保持します。表示や解析は行わず、live Provider の完全実行は通常 CI の必須条件にしません。
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


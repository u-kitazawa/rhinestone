# JAXA静的STACの実データ検証

調査日: 2026-10-14（日本時間）。対象: [Issue #211](https://github.com/u-kitazawa/rhinestone/issues/211)。
確認したdevelop: `d0cdf42cdff9f4d94a5588eda48915d154bb0af4`（PR #215取り込み後）。
これは調査記録であり、公開APIの正本・組み込みProviderの採用完了を示すものではありません。

## 公式情報と取得経路

- [公式ルートCatalog](https://data.earth.jaxa.jp/stac/cog/v1/catalog.json)
- [公式COG/STAC仕様](https://data.earth.jaxa.jp/api/python/v0.1.6/developer/database/)
- [データセット一覧](https://data.earth.jaxa.jp/en/datasets/)
- [研究データ等の利用条件](https://earth.jaxa.jp/ja/data/policy/)

公式仕様は静的な階層JSONとCOG配信を説明しています。STAC APIの `/search` ではありません。
ルートの `child` → Collectionの `child` → 時期 → COG level → 地域Catalogの
`item` → Itemの `assets` を実際に辿りました。Wasabiの配信先はルートJSONに
記載されたリンクから確認し、URIやasset keyを製品名から推測していません。
以下のCollection / Item / asset取得ではAuthorization header、APIキー、ログインを使用していません。

配信ベースURI（以下 `BASE`）:

```text
https://s3.ap-northeast-1.wasabisys.com/je-pds/cog/v1/
```

| 分野 | Collection ID / BASEからのCollectionパス | Collectionの範囲・時期 | 検証した時期 / data asset |
| --- | --- | --- | --- |
| 標高・DSM | `JAXA.EORC_ALOS.PRISM_AW3D30.v3.2_global/collection.json` | 全球、2021年2月 | `2021-02` / `DSM` |
| 降水 | `JAXA.EORC_GSMaP_standard.Gauge.00Z-23Z.v6_monthly/collection.json` | 経度-180～180、緯度-60～60、2000年3月以降 | `2021-02` / `PRECIP` |
| 土地被覆 | `JAXA.EORC_ALOS_HRLULC.v25.04_japan/collection.json` | 経度122～154、緯度20～46、2020～2024年 | `2024` / `HRLULC` |

検証した地域Catalogはそれぞれ `BASE + Collection ID + /時期/0/E000.00-E180.00/catalog.json`。
ItemはそのCatalogの `./S90.00-N90.00.json` リンク、assetはそのItemの相対hrefです。
level 0は900×900の低解像度配信であり、AW3Dの元データの30m解像度を検証したものではありません。
公式仕様のlevel/PPUと、元プロダクトの解像度を区別します。

## 観測したmetadataと利用条件

- AW3D ItemはSTAC 1.0.0、`DSM` はdata role、`MSK` はdata-mask role。現行検索はDSMを返し、MSKを選択しません。
- GSMaP ItemはSTAC 1.0.0。Collectionの `id` は `collection` ですが、Itemの `collection` は上表の製品IDです。
- HRLULC ItemはSTAC 1.1.0。COG profileのないGeoTIFF media typeも現行Adapterで `geotiff` として解決できます。
- 3つのlevel-0 Itemのbboxは `[0,-90,180,90]`。Collectionの実データ範囲とは異なります。Item bboxとの交差だけで、その地点に有効値があると保証しません。
- GSMaPのmonthly製品でも検証Itemの時間範囲は `2021-02-01T00:00:00.000000Z` ～ `2021-02-01T23:00:00.000000Z`。月全体へ補正して検索しません。time条件は広告されたmetadataに従うため、2月中旬の検索でこのItemが落ちる可能性があります。
- Collectionのlicenseは3つとも `proprietary`。ライセンスリンクはJAXAの研究データ利用条件を指します。認証不要と、無条件・CC0の利用許諾を混同しません。
- 利用条件はJAXAおよびデータ名の出所表示、他機関データを含む場合の追加出所表示を要求し、商用利用では事前連絡が必要としています。配布・可視化時は各プロダクトの条件も確認してください。

## 検索・配信・openの実測

限定した地域Catalogを `catalog_uri`、`max_documents=2` として公開 `configure()` 経路から、
`bbox=(139,35,140,36), limit=1` を検索しました。各ケースはCatalogとItemの2文書を取得し、
1 Resource、diagnosticsなし。検索の壁時計時間は約9～10秒でした（同時3ケース、環境・キャッシュ依存）。
以下のJSON byte数は別途GETした2文書の本文合計で、圧縮・headerを含むwire転送量ではありません。

| asset | media typeに基づくResource形式 | JSON本文合計 byte | asset HEAD / size byte | Rasterioで復号した結果 |
| --- | --- | ---: | --- | --- |
| DSM | `cog` | 3,329 | 200 / 634,026 | 900×900、1 band、EPSG:4326 |
| PRECIP | `geotiff` | 4,377 | 200 / 2,180,713 | 900×900、1 band、EPSG:4326 |
| HRLULC | `geotiff` | 7,384 | 200 / 10,626 | 900×900、1 band、EPSG:4326 |

全assetのHEADは `Accept-Ranges: bytes` を返しました。ただし直接GDAL経由のRange読み込みが
成功したとは扱いません。Rasterio 1.4.4 / 1.5.1での直接HTTP openは、この環境では
`unable to get local issuer certificate` により失敗しました。TLS検証の無効化は行っていません。

データ自体の復号確認は、標準ライブラリの検証付きHTTPS GETで取得し、3 MB上限を確認して
Rasterio `MemoryFile` へ渡す明示的なユーザーRuntimeで行いました。
Rhinestone CoreにRasterioやダウンロード機能は追加していません。
この経路で `resource.open` と独立コンテキストの `open(plan)` が両方成功しました。
1回の取得は約4～7秒、上表のasset全量を取得しています。大きなlevelへの自動適用はしません。
東京付近（139.7, 35.7）の1pixelはDSM=7、PRECIP≈0.10716835、HRLULC=2でした。
低解像度の値なので、局所地形や雨量の精度・分類精度の評価には使用しません。

検証用Runtimeの要点（通常CI・本番用ではありません）:

```python
from contextlib import contextmanager
from urllib.request import urlopen
import rasterio

class BoundedMemoryRasterio:
    @contextmanager
    def open(self, uri):
        with urlopen(uri, timeout=30) as response:
            body = response.read(3_000_001)
        if len(body) > 3_000_000:
            raise ValueError("manual validation download exceeds 3 MB")
        with rasterio.io.MemoryFile(body) as memory:
            with memory.open() as dataset:
                yield dataset
```

検索アプリの `app.plan(resource).to_dict()` をJSON化し `AccessPlan.from_dict()` で復元。
受信側は選択asset URIと形式だけを許可するdirect Providerを持ち、STAC Providerは持たない
独立した `configure()` コンテキストです。受信側のProvider再問い合わせなしで同じdatasetを
開けました。planは認可やRuntimeを代替せず、credentialやデータ本体も含みません。

## 国内の追加候補（確認済みと未確認を区別）

| 提供元 / 公式情報 | STAC提供の確認 | 認証・地域・分野・形式・利用条件・稼働/open | 採用判断 |
| --- | --- | --- | --- |
| JAXA Earth API（上記公式Catalog/仕様） | 静的型を実取得 | 認証なし、全球/日本、標高/降水/土地被覆、COG/GeoTIFF、proprietary・条件リンクあり、限定検索とMemoryFile open成功 | 検証候補。組み込み登録は探索改善・直接remote open確認後 |
| 産総研 [STAC整備の調達仕様書](https://www.aist.go.jp/aist_j/procure/supplyinfoold/detail/202410/TOIIN9B3/9CPRV6B7S9GGT3X5VIGN.pdf) | STAC準拠Catalog/API構築の記載あり。ただし公開Endpointの提供確認ではない | 公開Endpoint、認証、対象地域、形式、利用条件、稼働/openは未確認 | 未採用。調達資料だけで登録しない |
| 国土地理院 [標高API](https://maps.gsi.go.jp/development/elevation_s.html) | 確認したものは独自JSON APIでSTACではない。公式ドメインのSTAC検索でも公開STAC Endpointは未確認 | STACとしての認証・範囲・形式・利用条件・稼働/openは未確認 | STACとして未採用。STACが存在しないとは断定しない |

調査は公式ドメインのSTAC検索と資料確認による初期調査です。国内候補を網羅したものではありません。

## 登録前に残る作業

1. 現行BFSはItem取得後にだけbbox/time/collectionを適用します。ルートからの無差別探索を避ける
   一般的な枝刈り・選択方式を設計し、巨大階層・欠損extent・誤ったmetadataをfixtureで検証する。
   GSMaP Collectionには2000年以降の月次childが多数あり、既定100文書では後年のItem到達前に
   上限に達し得ます。Catalog IDの文字列から年月や解像度を推測する特例は追加しない。
2. JAXAのCOG level/解像度の選択とmonthly時間metadataの意味を確認する。
   `limit=1`が最初に見つけた低解像度を返すことを、高解像度の最適選択と説明しない。
3. 本番相当のRuntime/信頼ストアで直接HTTP openとRange読み込みを確認する。
4. 有界探索と初期応答時間を確認してから、組み込みCatalog・設定不要Showcaseを追加する。
5. 追加国内STACの公開Endpoint・条件を検証する。未確認Endpointは登録しない。

今回の回帰テストは `tests/test_jaxa_stac.py`。公式Itemの選択フィールドを縮約したfixtureで
STAC 1.0/1.1、相対asset、media type、role選択、bbox/time、2文書上限、
`search → open` と `plan → JSON → 独立open` をネットワークなしで検証します。
外部サービスの可用性は通常CIの必須条件にしません。

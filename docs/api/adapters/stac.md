# StacAdapter（STAC提供元アダプター）

`StacAdapter` は STAC API 1.0 と静的STAC Catalogの Item asset を解決します。

API型は`endpoint`から`/search`を呼びます。静的型は`catalog_uri`から公式の
`rel="child"` / `rel="item"`リンクだけを幅優先で辿り、同じURIを再取得しません。
`max_documents`（既定100）を超えて探索が完了しない場合は、不完全な検索結果を返さず
明示的に失敗します。相対リンクとasset hrefは、それぞれを含むレスポンスURIを基準に
解決されます。

標準文書（Catalog / Collection / Item）の解釈とLink / Assetの相対href解決は
PySTACへ委譲します。配布依存は拡張パッケージ群を含まない`pystac-core>=1.15.2,<2`
（import名は`pystac`）です。GIS Runtimeや`pystac-client`はCore依存へ追加しません。
HTTP取得・認証・destination policy、幅優先の探索・上限・訪問管理、検索条件、
assetの明示選択とResource/AccessPlan変換はRhinestoneが担当します。
PySTACの自動再帰探索・既定I/O・ネットワークschema検証・暗黙の旧版migrationは使いません。
未選択の親・root・collection・extension schemaへの追加通信は行いません。

取得時の文書はraw metadataにそのまま保持し、PySTACによる再シリアライズ結果で置換しません。
Itemの`stac_version`・`type`・日時等をPySTACが解釈できない場合、検索では
`item_skipped` / `invalid_item`、直接loadでは`ProviderResponseError`となります。
Catalog / Collectionの解釈失敗は応答全体の`ProviderResponseError`です。
これは全STAC schemaへの適合検証を保証するものではありません。
redirect後のURIも訪問済みとして管理し、同じ文書への別名リンクから重複候補を作りません。
文書内の`self`リンクより実際のレスポンスURIを相対解決の基準として優先します。

[Provider Adapter 一覧](../provider-adapters.md) · adapter type: `stac`

## 設定と検索

Provider の `settings` へAPI型は `endpoint`、静的型は `catalog_uri` を指定します。
直接loadのReferenceには `collection_id`、`item_id`、`asset_key` が必要です。
静的型ではItemの配信URIを `item_href` に指定します（検索結果のReferenceには保持済み）。
検索には `bbox`、`time`、`limit` を使えます。

組み込みCatalogには、追加設定やAPIキーなしで試せるJAXA Earthの
低解像度プレビューを用意しています。

| ProviderId / ID | データ | 固定期間 | data asset |
| --- | --- | --- | --- |
| `JAXA_GSMAP_PREVIEW` / `jaxa-gsmap-preview` | GSMaP月降水量 | 2021年2月 | `PRECIP` |
| `JAXA_AW3D_PREVIEW` / `jaxa-aw3d-preview` | AW3D30 v3.2の標高 | 2021年2月 | `DSM` |
| `JAXA_HRLULC_PREVIEW` / `jaxa-hrlulc-preview` | HRLULC v25.04の土地被覆 | 2024年 | `HRLULC` |

大規模なJAXAルートCatalogを走査せず、各製品のlevel 0・東経0〜180度の階層を
Provider設定で直接指定し、それぞれ取得上限を2文書に固定しています。
固定期間は配信階層の期間であり、標高等の観測日時を意味しません。
これはJAXA全製品・全期間を検索するProviderではありません。
検索の`bbox`はItemを選ぶ条件であり、開いたラスタの切り出しではありません。

```python
from datetime import datetime, timezone

from rhinestone import ProviderId, search

results = search(
    providers=[ProviderId.JAXA_GSMAP_PREVIEW],
    bbox=(139.0, 35.0, 140.0, 36.0),
    time=(
        datetime(2021, 2, 1, tzinfo=timezone.utc),
        datetime(2021, 2, 28, tzinfo=timezone.utc),
    ),
    limit=1,
)
resource = results[0]
```

上の例を`ProviderId.JAXA_AW3D_PREVIEW`へ変更すると同期間の標高を検索できます。
土地被覆は`ProviderId.JAXA_HRLULC_PREVIEW`を選び、`time`も2024年内に変更してください。
対象Providerだけを明示選択でき、結果のReferenceは表の`asset_key`を保持し、
そのassetのURIをResourceとAccessPlanへ引き継ぎます。

AW3Dの`DSM`は標高（m）、HRLULCは分類IDです。HRLULCの分類IDを
連続値として平均せず、縮小表示時は最近傍など分類を保つ方法を使ってください。
NoData値・単位・分類の意味は配信metadataと製品仕様を確認します。
低解像度プレビューは原解像度の解析用データと同等ではありません。

利用前に[JAXA Earthの利用条件](https://earth.jaxa.jp/en/data/policy/)と
各製品の条件（[AW3D30](https://www.eorc.jaxa.jp/ALOS/aw3d30/terms)、
[HRLULC](https://www.eorc.jaxa.jp/ALOS/lulc/terms.htm)）を確認してください。
キーなしで取得できることは無条件利用を意味しません。
出典表示や商用利用時の事前連絡など、適用される条件に従ってください。
公開成果では[Earth APIの案内](https://data.earth.jaxa.jp/ja/)に従い、その利用も明記します。

API型の`features`配列に混在する非object値や不正Itemは、
`item_skipped` / `invalid_item`の診断付きで除外し、正常なItemの結果順とmetadataを保持します。
`features`自体の欠落、またはobject・nullなどの配列以外の値は、
応答全体の`ProviderResponseError`として扱います。

静的型のbbox交差判定はItemの4座標bboxを使います。検索範囲またはItemが日付変更線を
跨ぐ場合（`west > east`）も両側の経度区間を比較し、接する境界を含めます。
`180°`と`-180°`は同じ境界として扱います。
これはbboxによる絞り込みであり、geometryの厳密な交差判定ではありません。
日付変更線跨ぎの表現は[OGC API Featuresのbbox仕様](https://docs.ogc.org/is/17-069r4/17-069r4.html#_parameter_bbox)
および[STAC APIの検索例](https://github.com/radiantearth/stac-api-spec/blob/release/v1.0.0/item-search/examples.md)に従います。

静的型のbbox/time/collection条件はItem取得後に適用します。Collectionのextentや
CatalogのIDから子階層を事前に絞り込む機能はありません。`limit`は返すResource数の
上限であり、Itemに到達するまでのHTTPリクエスト数を保証しません。
大規模なルートCatalogを指定する前に、対象階層と `max_documents` を確認してください。
上限の増加だけで大規模Catalogの応答時間を解決できるとは限りません。

`collection_id` と `item_id` は未エンコードの論理IDとして指定します。RhinestoneはHTTP requestを組み立てる際に各IDを1つのpath segmentとしてpercent-encodeします。既にエンコードされたように見える値も推測で復号しないため、例えば論理IDの`%2F`はrequest pathでは`%252F`になります。`.`と`..`だけのIDもpath traversalとして正規化されないようエンコードします。Metadataとprovenanceには元の論理IDを保持します。

## 接続先と認証

Item、Search、静的Catalogの取得はRhinestoneの組み込みHTTP transportで行います。
Adapterを直接構築する場合も、`credential`に論理名を指定し、`credentials`の
CredentialRegistryから認証情報を取得します。API型・静的型のどちらもdata roleの各assetを
独立Resourceとして返します。複数assetのItemも返し、先頭assetを暗黙選択しません。
data assetがないItemや不正Item等の理由は検索結果の `diagnostics` で確認できます。
asset formatはmedia typeに基づき、URLやファイル名から推測しません。

Assetの`href`がrelative URI referenceの場合は、そのAssetを含むItem responseの最終URI（HTTP redirect後を含む）を基準にRFC 3986の規則でabsolute URIへ解決します。元の`href`はraw metadataに保持し、解決済みURIをResourceとprovenanceの`original_url`に使用します。認証付きリクエストでは、認証情報が別originへ転送されないようredirectを許可しません。

## 解決して Rasterio で開く例

```python
from rhinestone.catalogs import Catalog
import rasterio

from rhinestone import Reference, Provider, configure

app = configure(
    catalog=Catalog(
        (
            Provider(
                id="imagery",
                adapter_type="stac",
                settings={"endpoint": "https://stac.example/api"},
            ),
        )
    ),
)
resource = app.load(
    Reference(
        "imagery",
        parameters={
            "collection_id": "collection-id",
            "item_id": "item-id",
            "asset_key": "asset-key",
        },
    )
)
with resource.open("rasterio", runtime=rasterio) as dataset:
    print(dataset.width, dataset.height)
```

値は STAC API が返す collection、Item、asset の識別子を使います。実在 API を使う環境変数ベースの手順は、リポジトリ checkout の `examples/06_stac_cog/README.md` を参照してください。

# StacAdapter（STAC提供元アダプター）

`StacAdapter` は STAC API 1.0 と静的STAC Catalogの Item asset を解決します。

API型は`endpoint`から`/search`を呼びます。静的型は`catalog_uri`から公式の
`rel="child"` / `rel="item"`リンクだけを幅優先で辿り、同じURIを再取得しません。
`max_documents`（既定100）を超えて探索が完了しない場合は、不完全な検索結果を返さず
明示的に失敗します。相対リンクとasset hrefは、それぞれを含むレスポンスURIを基準に
解決されます。

[Source Adapter 一覧](../source-adapters.md) · source type: `stac`

## 設定と検索

Provider の `settings` へAPI型は `endpoint`、静的型は `catalog_uri` を指定します。
直接loadのReferenceには `collection_id`、`item_id`、`asset_key` が必要です。
静的型ではItemの配信URIを `item_href` に指定します（検索結果のReferenceには保持済み）。
検索には `bbox`、`time`、`limit` を使えます。

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

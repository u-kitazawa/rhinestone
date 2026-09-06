# EStatAdapter

`EStatAdapter` は e-Stat API 3.0 の統計表 metadata を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `estat`

## 設定と検索

`Config.settings` の必須項目は `stats_data_id` です。endpoint と language は `sources.ESTAT` の Catalog 定義から渡されます。検索条件は `text` と `limit` です。

## Endpoint と認証

解決には `getMetaInfo`、検索には `getStatsList` を使います。HTTP通信はRhinestoneの組み込みtransportを使い、利用者はlogical credential `estat` だけを注入します。認証情報は Provenance に保存されません。

## 解決する例

```python
import os

from rhinestone import Config, configure, sources

app = configure(
    sources=(sources.ESTAT,),
    credentials={"estat": lambda: os.environ["ESTAT_APP_ID"]},
)
resource = app.resolve(Config("estat", {"stats_data_id": "table-id"}))
```

`stats_data_id` は統計表の `statsDataId` です。統計コードの `statsCode` ではありません。application ID の取得を含む手順は、リポジトリ checkout の `examples/03_estat_population/README.md` を参照してください。この Adapter は metadata を解決しますが、統計値を読む built-in Execution Adapter はありません。

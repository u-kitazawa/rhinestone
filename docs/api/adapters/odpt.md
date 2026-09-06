# OdptAdapter

`OdptAdapter` は ODPT v4 の service query を解決します。データ取得は行わず、
`JsonServiceAdapter` が実行します。

[Source Adapter 一覧](../source-adapters.md) · source type: `odpt`

## 設定

`dataset`（`station`、`railway`、`train`）と logical credential 名の `credential` が
必須です。公式フィールドだけを含む `filters` は任意です。

## Endpoint と実行

endpoint は `https://api.odpt.org/api/v4/` 配下の `odpt:Station`、`odpt:Railway`、
`odpt:Train` に固定です。AdapterはRhinestoneが構成するため、provider、requests互換
runtime、credential factoryだけを登録します。

```python
from rhinestone import ProviderConfig, configure

app = configure(
    providers={"odpt": ProviderConfig("odpt")},
    dependencies={"json-service": lambda: requests},
    credentials={"odpt": lambda: os.environ["ODPT_CONSUMER_KEY"]},
)
```

`acl:consumerKey` は open 時に credential factory から取得し、Config や Source には保存しません。

## 駅を取得する例

```python
records = app.open(
    Config(
        "odpt",
        {
            "dataset": "station",
            "credential": "odpt",
            "filters": {"dc:title": "東京"},
        },
    )
)
```

この例の `"odpt"` は `credentials={"odpt": ...}` の key と一致させます。consumer key
そのものではありません。`app` の構成を含む完全な例は、リポジトリ checkout の
`examples/12_odpt_station/README.md` を参照してください。

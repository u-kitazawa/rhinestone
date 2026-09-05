# OdptAdapter

`OdptAdapter` は ODPT v4 の service query を解決します。データ取得は行わず、
`JsonServiceAdapter` が実行します。

[Source Adapter 一覧](../source-adapters.md) · source type: `odpt`

## 設定

`dataset`（`station`、`railway`、`train`）と logical credential 名の `credential` が
必須です。公式フィールドだけを含む `filters` は任意です。

## Endpoint と実行

endpoint は `https://api.odpt.org/api/v4/` 配下の `odpt:Station`、`odpt:Railway`、
`odpt:Train` に固定です。次のように request preparer と credential factory を登録します。

```python
from rhinestone.adapters import OdptAdapter
from rhinestone.adapters.execution import JsonServiceAdapter

source = OdptAdapter()
execution = JsonServiceAdapter(OdptAdapter.prepare_request, "odpt")
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

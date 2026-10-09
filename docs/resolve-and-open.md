# Resourceを開く

通常は検索結果のResourceをそのまま開けます。

```python
import rasterio
from rhinestone import ProviderId, search

resource = search(text="標準地図", providers=[ProviderId.GSI], limit=1)[0]
with resource.open("rasterio", runtime=rasterio) as dataset:
    ...
```

独自構成では`app.open(resource, "rasterio", runtime=rasterio)`を使います。
AccessPlanがない検索結果はReferenceからloadしてから実行します。
形式を確定できない場合は`ExecutionAdapterUnavailableError`となり、別の形式やRuntimeへ
自動で切り替えません。Rhinestoneはデータ解析や形式変換を行いません。

## 既知の対象を読み込む

```python
from rhinestone import Reference, configure

app = configure()
resource = app.load(
    Reference(
        "direct",
        parameters={
            "uri": "https://example.invalid/data.geojson",
            "format": "geojson",
            "media_type": "application/geo+json",
        },
    )
)
```

## 実行契約を転送する

```python
from rhinestone import AccessPlan

payload = app.plan(resource).to_dict()
plan = AccessPlan.from_dict(payload)
data = receiving_app.open(plan, "pyogrio", runtime=pyogrio)
```

通常のopenではplan取得は不要です。受信側はProviderへ再問い合わせせず、自身の
DestinationPolicyとCredential factoryで実行を認可します。Runtimeやsecretは転送しません。

## Runtimeの指定

Adapter名と対応するRuntime実体は必須です。Execution Runtimeは`configure()`へ登録せず、
`open(..., runtime=...)`へ渡します。`RuntimeFactory`は実行用には使えません。
ODPTのJSONサービスはCoreのRuntimeを使うため`open("json-service")`で開きます。

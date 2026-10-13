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

## 検索・解決・実行のエラー境界

検索できること、Resourceへ解決できること、Runtimeで開けることは別々の契約です。
失敗した段階に応じて、次の例外を使い分けます。

| 段階 | 代表的な失敗 | 例外 | 対応 |
| --- | --- | --- | --- |
| 検索 | Providerへの接続・認証・応答形式 | `ProviderMetadataError` / `ProviderResponseError` | Provider設定や応答を確認する |
| 解決 | 候補なし・候補が複数・AccessPlanを確定できない | `ResourceNotFoundError` / `AmbiguousResourceError` / `UnsupportedAccessError` | 明示的なResource選択や形式を指定する |
| 実行準備 | 対応AdapterまたはRuntimeがない | `ExecutionAdapterUnavailableError` | 対応するAdapter・形式・Runtimeを指定する |
| 実行 | 選択済みデータをRuntimeが開けない | `ResourceAccessError` | URI、権限、Runtimeのdriver対応、元の例外を確認する |
| 実行認可 | 接続先がDestinationPolicyで許可されない | `DestinationNotAllowedError` | 信頼済み接続先とpolicy設定を確認する |

`ResourceAccessError`はResourceと実行Adapterの選択後に発生します。GDALなどのRuntimeが
返した例外は`__cause__`へ保持されます。一方、Adapter自身が不正なAccessPlanや
「データセットなし」を検出した場合は、回復方法を含む元の`ResourceAccessError`を
そのまま返します。資格情報やその値を例外メッセージへ含めてはいけません。

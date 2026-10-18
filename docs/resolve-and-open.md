# Resourceを開く

通常は検索結果のResourceを、対応するAdapterとRuntimeを明示して開けます。
次の例ではGDALを用意し、国土地理院のXYZタイルをGDALのWMS/XYZ定義へ翻訳して開きます。

```python
from osgeo import gdal
from rhinestone import ProviderId, search

resource = search(text="標準地図", providers=[ProviderId.GSI], limit=1)[0]
dataset = resource.open("gdal", runtime=gdal)
print("URI:", resource.uri)
print("raster size:", dataset.RasterXSize, dataset.RasterYSize)
```

独自構成では`app.open(resource, "gdal", runtime=gdal)`を使います。
Rasterio AdapterはCOG/GeoTIFFを対象とし、このXYZタイルには対応しません。
Adapterごとの対応形式は[対応状況](compatibility.md)を参照してください。
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
`app.open()`と`resource.open()`のAdapter名は空でない文字列が必須です。
`None`・不正型・空文字・空白のみは、loadやRuntime実行より前に`ConfigValidationError`になります。
`None`を自動選択の指定としては扱いません。非空の未登録名・非互換名は引き続き
`ExecutionAdapterUnavailableError`です。

## 検索・解決・実行のエラー境界

検索できること、Resourceへ解決できること、Runtimeで開けることは別々の契約です。
失敗した段階に応じて、診断または例外を使い分けます。

| 段階 | 代表的な失敗 | 観測結果 | 対応 |
| --- | --- | --- | --- |
| 検索 | Providerへの接続・認証・応答形式 | `SearchResults.diagnostics`の`reason="provider_failure"` | `failure_type`からmetadata・response・credentialを判別する |
| 解決 | 候補なし・候補が複数・AccessPlanを確定できない | `ResourceNotFoundError` / `AmbiguousResourceError` / `UnsupportedAccessError` | 明示的なResource選択や形式を指定する |
| 実行準備 | 対応AdapterまたはRuntimeがない | `ExecutionAdapterUnavailableError` | 対応するAdapter・形式・Runtimeを指定する |
| 実行 | 選択済みデータをRuntimeが開けない | `ResourceAccessError` | URI、権限、Runtimeのdriver対応、元の例外を確認する |
| 実行認可 | 接続先がDestinationPolicyで許可されない | `DestinationNotAllowedError` | 信頼済み接続先とpolicy設定を確認する |

検索時のProvider障害はSource単位で隔離され、他のSourceの結果とともに返ります。
全Sourceが失敗した場合も、空の`SearchResults`とdiagnosticsを返します。
Adapterが形式に対応していても、利用環境のdriver、ZIP内の対象ファイル、データ配信先の
可用性や認証まで保証するものではありません。これらの実データアクセス失敗は
`ResourceAccessError`として扱い、別のResourceやRuntimeへ自動で切り替えません。
`ResourceAccessError`はResourceと実行Adapterの選択後に発生します。GDALなどのRuntimeが
返した例外は`__cause__`へ保持されます。一方、Adapter自身が不正なAccessPlanや
「データセットなし」を検出した場合は、回復方法を含む元の`ResourceAccessError`を
そのまま返します。資格情報やその値を例外メッセージへ含めてはいけません。

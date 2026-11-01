# GdalAdapter（GDAL実行アダプター）

`GdalAdapter` は選択済み AccessPlan を利用者提供の GDAL runtime へ渡します。

[Runtime Adapter 一覧](../runtime-adapters.md) · 選択名: `gdal` · priority: `20`

## 対応形式とRuntime

Shapefile、GeoTIFF、COG、NetCDF、WMS、GML、KML、CityGML、GSI XYZ tile を扱います。
runtime は `OpenEx(uri, open_options=...)` を提供する必要があります。

ZIP は `/vsizip/`、リモート ZIP は `/vsicurl/` URI に変換し、確定済み encoding を
open option として渡します。Resource の再選択、解析、形式・CRS 変換は行いません。

URI、encoding、XYZ tile設定はAccessPlanから取得します。driverは固定しません。
対応形式でもRuntimeのdriverや実データによって開けない場合は`ResourceAccessError`になります。
GDALがデータセットを返さない場合も同じエラーとし、Runtimeの例外は`__cause__`へ保持します。

参考: [GDALのセキュリティに関する注意](https://gdal.org/en/stable/user/security.html)

## HTTPSラスタの部分読込を明示する

通常のHTTPS URIはそのまま`OpenEx`へ渡します。GDALのHTTP pseudo-driverは
ファイル全体をメモリへ取得するため、小さいwindowや出力配列だけでは転送量を制限できません。
`/vsicurl/`はHTTP Rangeを使う別の経路です。配信サーバーのRange対応、ファイルの配置、
GDALのキャッシュ等に依存するため、部分読込でも出力配列と同じ通信量にはなりません。

選択済みの静的HTTPS GeoTIFF/COGにRange対応が確認できている場合、
利用者側Runtimeで明示できます。以下の`resource`は検索等で選択済みのラスタです。
このRuntimeは、そのURIだけを許可します。GDALのTLS/CA・proxy設定は利用環境で準備します。

```python
import json
from types import SimpleNamespace

from osgeo import gdal

from rhinestone import AccessPlan, Catalog, Provider, configure

if resource.format not in {"geotiff", "cog"} or not resource.uri.startswith("https://"):
    raise ValueError("この例は選択済みの静的HTTPS GeoTIFF/COGを対象にします")
allowed_uri = resource.uri


def open_with_ranges(uri, **options):
    if uri != allowed_uri:
        raise ValueError("選択した配信URI以外は許可しません")
    return gdal.OpenEx("/vsicurl/" + uri, **options)


range_runtime = SimpleNamespace(OpenEx=open_with_ranges)
dataset = resource.open("gdal", runtime=range_runtime)
print(dataset.RasterXSize, dataset.RasterYSize)
dataset = None  # 読取後はGDALのdatasetを解放します

plan_json = json.dumps(configure().plan(resource).to_dict())
received_plan = AccessPlan.from_dict(json.loads(plan_json))
receiving_app = configure(
    catalog=Catalog((Provider(
        "permitted-raster", "direct", {"uri": allowed_uri, "format": resource.format}
    ),)),
)
received_dataset = receiving_app.open(received_plan, "gdal", runtime=range_runtime)
print(received_dataset.RasterXSize, received_dataset.RasterYSize)
received_dataset = None
```

`/vsicurl/`への翻訳は利用者側Runtimeの呼出時だけで行い、ResourceとPlanには元のHTTPS URIを
保持します。受信側の許可も元の配信URI/形式に対して行います。PlanだけではRuntimeや
GDALの信頼設定は転送されません。この例を動的API、WMS、ZIP、Range非対応サーバーへ
一律に適用せず、対象ごとに既存のRuntime契約を確認してください。

参考: [GDALのHTTP・VSI読込方式](https://gdal.org/en/stable/user/virtual_file_systems.html)

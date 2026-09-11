# GdalAdapter

`GdalAdapter` は選択済み Resource を利用者提供の GDAL runtime へ渡します。

[Execution Adapter 一覧](../execution-adapters.md) · 選択名: `gdal` · priority: `20`

## 対応と runtime

Shapefile、GeoTIFF、COG、NetCDF、WMS、GML、CityGML、GSI XYZ tile を扱います。
runtime は `OpenEx(uri, open_options=...)` を提供する必要があります。

ZIP は `/vsizip/`、リモート ZIP は `/vsicurl/` URI に変換し、確定済み encoding を
open option として渡します。Resource の再選択、解析、形式・CRS 変換は行いません。

`network_policy="strict"` では、通常の Resource は `resource.uri`、XYZ tile は
`access_plan.options["tile"]["url"]` も実際の送信先として、GDAL 用 XML を生成する前に
Catalog 由来の destination policy で認可します。認可されていない host や path、
HTTP(S) 以外の tile URL は `OpenEx()` を呼ぶ前に拒否します。

Resource URIが `/vsicurl/`、`/vsicurl_streaming/`、または`/vsizip/`等のarchive
wrapperを組み合わせたlocatorの場合は、内側のHTTP(S) URLを認可します。通常のlocal
pathと既知のlocal VSI locatorは維持し、認識できない`/vsi.../`構文はstrict policyで
fail closedにします。

さらに`strict`では、remote HTTP(S) Resourceをuser-owned Runtimeへ渡しません。Runtime内部の
redirect destinationをRhinestoneが再認可できないためです。local Resourceは利用できます。
GeoTIFF／COGだけを`allowed_drivers=("GTiff",)`で開きます。
拡張子と実際のdriverは一致する保証がなく、VRTやWMS等は内部で別datasetを開けるためです。
Shapefile、NetCDF、WMS、GML、CityGML、XYZ tileは、secondary accessを同じpolicyで
再認可できるRuntime契約がない限り`strict`ではRuntime解決前に拒否します。
`credentialed`／`none`では従来どおりGDALのdriver discoveryを利用します。

参考: [GDAL Security considerations](https://gdal.org/en/stable/user/security.html)

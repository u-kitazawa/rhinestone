# PyogrioAdapter

`PyogrioAdapter` は選択済み vector Resource を利用者提供の pyogrio runtime で読み込みます。

[Execution Adapter 一覧](../execution-adapters.md) · 選択名: `pyogrio` · priority: `10`

Shapefile、GeoJSON、GeoPackage、FlatGeobuf に対応します。runtime は
`read_dataframe(uri, **options)` を提供する必要があります。確定済みの `encoding` は
option として渡されます。archive URI の組み立ては行いません。

`network_policy="strict"`では、GDAL VSI locatorに埋め込まれたHTTP(S) URLもCatalog由来の
destination policyで認可します。未認可URLと認識できない`/vsi.../`構文は
`read_dataframe()`を呼ぶ前に拒否します。
remote HTTP(S) ResourceはRuntime内部のredirectを再認可できないため、`strict`では
`read_dataframe()`へ渡しません。local Resourceと`credentialed`／`none`は従来どおりです。

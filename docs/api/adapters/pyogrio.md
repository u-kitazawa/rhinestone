# PyogrioAdapter（pyogrio実行アダプター）

`PyogrioAdapter` は選択済み vector Resource を利用者提供の pyogrio runtime で読み込みます。

[Execution Adapter 一覧](../execution-adapters.md) · 選択名: `pyogrio` · priority: `10`

Shapefile、GeoJSON、GeoPackage、FlatGeobuf に対応します。runtime は
`read_dataframe(uri, **options)` を提供する必要があります。確定済みの `encoding` は
option として渡されます。archive URI の組み立ては行いません。

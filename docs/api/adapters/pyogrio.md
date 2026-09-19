# PyogrioAdapter（pyogrio実行アダプター）

`PyogrioAdapter` は選択済み vector Resource を利用者提供の pyogrio runtime で読み込みます。

[Execution Adapter 一覧](../execution-adapters.md) · 選択名: `pyogrio` · priority: `10`

Rhinestone の representation registry で `vector` と明示された Shapefile、GeoJSON、
GeoPackage、FlatGeobuf、GML、KML、CityGML に対応します。runtime は
`read_dataframe(uri, **options)` を提供する必要があります。確定済みの `encoding` は
option として渡されます。archive URI の組み立ては行いません。

この選択は Source Adapter が明示した `Resource.format` だけに基づきます。URL suffix や
archive の内容は調べません。選択できても、利用者の pyogrio/GDAL 環境に対応 read driver が
ない場合や、geometry / field type を読めない場合は、`open()` が `ResourceAccessError` を
送出します。

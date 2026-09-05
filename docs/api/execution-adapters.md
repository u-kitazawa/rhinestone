# Execution Adapter

Execution Adapter は選択済みの `Resource` を、利用者が供給する runtime の API
呼び出しへ変換します。Resource の選択やデータ形式の変換は行いません。

[API リファレンス](../api.md) · [Source Adapter](source-adapters.md)

登録方法と `resource.open()` の使い方は[Resource を解決して開く](../resolve-and-open.md)
を参照してください。runtime dependency は `dependencies` に factory として渡します。

| Adapter | 選択名 / dependency 名 | runtime |
| --- | --- | --- |
| [GDAL](adapters/gdal.md) | `gdal` | `OpenEx` |
| [Rasterio](adapters/rasterio.md) | `rasterio` | `open` |
| [pyogrio](adapters/pyogrio.md) | `pyogrio` | `read_dataframe` |
| [JSON service](adapters/json-service.md) | `json-service` | requests 互換の `get` |

独自 Adapter は `ExecutionAdapter` を継承し、`name`、`priority`、
`supports(resource, dependencies)`、`open(resource, runtime)` を実装します。

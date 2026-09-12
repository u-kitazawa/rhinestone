# Execution Adapter（実行アダプター）

Execution Adapter は選択済みの `Resource` を実行runtimeのAPI呼び出しへ変換します。Resource の選択やデータ形式の変換は行いません。

[API リファレンス](../api.md) · [Source Adapter](source-adapters.md)

実装チュートリアルは[Custom Adapter を作る](../custom-adapters.md)を参照してください。

外部Runtimeの供給方法と `resource.open()` の使い方は[Resource を解決して開く](../resolve-and-open.md)
を参照してください。GDAL等の外部Runtimeは `dependencies` に実体として渡し、遅延評価する
場合は `RuntimeFactory(factory)` を使います。bare callableはRuntime実体として扱われます。
JSON serviceのHTTP runtimeはRhinestoneが組み込みで提供します。依存境界とSourceごとの採用方針は[外部ライブラリ依存方針](../dependency-policy.md)を参照してください。

| アダプター | 選択名／Runtime名 | 呼び出す操作 |
| --- | --- | --- |
| [GDAL](adapters/gdal.md) | `gdal` | `OpenEx` |
| [Rasterio](adapters/rasterio.md) | `rasterio` | `open` |
| [pyogrio](adapters/pyogrio.md) | `pyogrio` | `read_dataframe` |
| [JSONサービス](adapters/json-service.md) | `json-service` | 組み込みHTTP通信 |

独自 Adapter は `ExecutionAdapterDefinition` として明示登録します。factory が返す Adapter は
`name`、`priority`、`supports(resource, dependencies)`、`open(resource, runtime)` を実装します。
基底クラスの継承は必須ではありません。Runtime と DestinationPolicy は
`ExecutionAdapterContext` から取得できます。

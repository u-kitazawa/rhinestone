# JsonServiceAdapter

`JsonServiceAdapter` は選択済み JSON service query をHTTP runtimeへ渡します。標準の`configure()`経路ではRhinestoneの組み込みruntimeが使われます。

[Execution Adapter 一覧](../execution-adapters.md) · 選択名: `json-service` · priority: `10`

`ServiceQueryPlan`、`application/json`、一致する service 名が必要です。組み込みruntimeはAdapterが要求する次の`get`契約を実装します。

```python
get(uri, params=..., headers=..., timeout=30, allow_redirects=False)
```

ODPT向けのAdapterとrequest preparer、HTTP runtimeはRhinestoneが自動構成します。redirect は拒否し、secret を含む可能性のある下位例外は公開しません。

`JsonServiceAdapter`を直接利用するテストや高度な用途では、同じ`get`契約を満たすruntimeを`open()`へ渡せます。

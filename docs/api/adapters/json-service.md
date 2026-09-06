# JsonServiceAdapter

`JsonServiceAdapter` は選択済み JSON service query を requests 互換 runtime へ渡します。

[Execution Adapter 一覧](../execution-adapters.md) · 選択名: `json-service` · priority: `10`

`ServiceQueryPlan`、`application/json`、一致する service 名、注入済み runtime が必要です。
runtime は次の形の `get` を提供します。

```python
get(uri, params=..., headers=..., timeout=30, allow_redirects=False)
```

ODPT向けのAdapterとrequest preparerはRhinestoneが自動構成します。
redirect は拒否し、secret を含む可能性のある下位例外は公開しません。

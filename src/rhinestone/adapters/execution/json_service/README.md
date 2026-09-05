# JSON Service Execution Adapter

`JsonServiceAdapter` は選択済み JSON service query を requests 互換 runtime へ渡します。

- `name`: `json-service`、優先度: `10`
- 対応条件: `ServiceQueryPlan`、`application/json`、一致する service 名、注入済み runtime
- 注入: request を作る callback、service 名、任意の `CredentialRegistry`
- runtime: `get(uri, params=..., headers=..., timeout=30, allow_redirects=False)`

redirect は拒否し、secret を含む可能性のある下位例外は公開しません。JSON schema の検証以外の変換は行いません。

# JSONサービスの実行アダプター

`JsonServiceAdapter` は選択済み JSON service query をHTTP runtimeへ渡します。標準の`configure()`経路ではRhinestoneの組み込みruntimeを使用します。

- `name`: `json-service`、優先度: `10`
- 対応条件: `ServiceQueryPlan`、`application/json`、一致する service 名
- 注入: request を作る callback、service 名、任意の `CredentialRegistry`
- Runtimeの契約: `get(uri, params=..., headers=..., timeout=30, allow_redirects=False)`

redirect は拒否し、secret を含む可能性のある下位例外は公開しません。JSON schema の検証以外の変換は行いません。Adapter単体では同じcontractを満たすruntimeを直接渡せます。

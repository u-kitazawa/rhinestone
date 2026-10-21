# JSONサービスの実行アダプター

`JsonServiceAdapter` は選択済み JSON service query をHTTP runtimeへ渡します。標準の`configure()`経路ではRhinestoneの組み込みruntimeを使用します。

- `name`: `json-service`、優先度: `10`
- 対応条件: `kind="service-query"`の`AccessPlan`、`application/json`、一致するservice名
- 注入: request を作る callback、service 名、任意の `CredentialPort`
- Runtimeの契約: `get(uri, params=..., headers=..., timeout=30, allow_redirects=False)`

redirect は拒否し、secret を含む可能性のある下位例外は公開しません。JSON schema の検証以外の変換は行いません。Adapter単体では同じcontractを満たすruntimeを直接渡せます。

ODPT の組み込み callback は同じ実行パッケージの `odpt.prepare_odpt_request` です。
提供元の `OdptAdapter` は Plan 生成だけを担当し、JSON サービス実行から呼び出しません。
`JsonServiceAdapter` が DestinationPolicy を検査した後、callback が Plan の service・endpoint・
params を検査してから論理 credential を解決します。endpoint の自己一致だけで送信先を認可しません。

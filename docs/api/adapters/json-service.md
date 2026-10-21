# JsonServiceAdapter（JSONサービス実行アダプター）

`JsonServiceAdapter` は選択済み JSON service query をHTTP runtimeへ渡します。標準の`configure()`経路ではRhinestoneの組み込みruntimeが使われます。

[Runtime Adapter 一覧](../runtime-adapters.md) · 選択名: `json-service` · priority: `10`

`kind="service-query"`のAccessPlan、`application/json`、一致するservice名が必要です。
組み込みruntimeはAdapterが要求する次の`get`契約を実装します。

```python
get(uri, params=..., headers=..., timeout=30, allow_redirects=False)
```

ODPT向けのAdapterとrequest preparer、HTTP runtimeはRhinestoneが自動構成します。redirect は拒否し、secret を含む可能性のある下位例外は公開しません。

ODPT の request preparer は
`rhinestone.adapters.runtime.json_service.odpt.prepare_odpt_request` です。
提供元 Adapter のインスタンスや static method に依存せず、Plan と `CredentialPort` を受け取ります。
実行時は、DestinationPolicy による宛先認可 → Plan の service・endpoint・params の検査 →
credential の取得 → HTTP 送信の順に処理します。Plan に記録された endpoint 自体を認可の根拠にはしません。

`JsonServiceAdapter`を直接利用するテストや高度な用途では、同じ`get`契約を満たすruntimeを`open()`へ渡せます。

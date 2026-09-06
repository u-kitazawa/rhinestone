# StaticAdapter

`StaticAdapter` は、リポジトリまたは利用者が管理する静的なサービス定義を
`Source` として解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `static`

## 設定

`Config.settings` には定義済みitemの `id` を指定します。

```python
Config("gsi", {"id": "std"})
```

定義はHTTP通信、runtime dependency、credentialを使わず、同じ設定から常に同じ
`Source` と `AccessPlan` を生成します。検索条件は `text` と `limit` です。

標準の国土地理院タイル定義は `sources.GSI` に含まれます。定義にはURL、形式、
ズーム範囲、帰属表示、利用条件URL、仕様確認日を含みます。

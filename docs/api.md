# API reference

このページは通常利用する公開APIを先に説明します。Adapter、Resolver、AccessPlan、Registryなどの内部構造は[用語と概念](concepts.md)とarchitecture文書を参照してください。

## `Catalog`

Providerのimmutableな集合です。組み込みCatalogは`rhinestone.catalogs.BUILTIN`です。

```python
from rhinestone.catalogs import BUILTIN
```

## `Provider`

Catalogからアプリケーションへ登録するデータ提供元です。

```python
from rhinestone import Provider

provider = Provider(
    id="my-stac",
    adapter_type="stac",
    settings={"endpoint": "https://stac.example/api"},
)
```

`adapter_type`と`settings`はProviderを構成する拡張向け情報です。secretやRuntimeは保持しません。

## `configure()`

Catalog、Runtime、Credentialを組み合わせて`Rhinestone`アプリケーションを作ります。

```python
from rhinestone import configure
from rhinestone.catalogs import BUILTIN

app = configure(
    catalog=BUILTIN,
    dependencies={"rasterio": rasterio},
    credentials={"odpt": lambda: odpt_key},
    network_policy="credentialed",
)
```

| 引数 | 説明 |
| --- | --- |
| `catalog` | 利用するProviderのCatalog |
| `sources` | `catalog`を使わない場合のProvider iterable。互換・高度な指定 |
| `dependencies` | 利用者が所有するSource / Execution Runtime。公開引数は共通だが内部では利用段階ごとに分離される |
| `credentials` | Credential factory |
| `network_policy` | 宛先制限。`none`、`credentialed`（既定）、`strict` |

通常のコードでは`catalog`を使ってください。`sources`はCatalogを使わない互換・高度な指定として利用できます。
Runtime factoryは`configure()`では評価されません。Source Runtimeは検索・解決時、
Execution Runtimeは`Resource.open()`時に、それぞれ初めて必要になった段階で評価されます。

Provider の `settings` に `credential` を論理名として指定すると、CKAN、STAC、OGC
などの HTTP Source へ Credential factory を遅延注入できます。secret 自体は
Provider、Catalog、Result、Resource には保存されません。`credentialed` と `strict`
では、factory の評価前に Catalog 由来の endpoint へ送信できることを検証します。

## `Rhinestone.search()`

検索パラメータからResultを返します。

```python
results = app.search(text="河川", limit=10)
result = results[0]
```

`text`、`bbox`、`time`、`limit`をキーワードで指定できます。`SearchQuery`を渡す形式は高度なAPIです。

## `Result`

検索で見つかった候補です。通常は次のようにResourceへ解決します。

```python
resource = app.resolve(result)
```

`title`、`description`、`discovered_by`、`target`、`metadata`、`provenance`を参照できます。`target`は解決先の`Config`で、`to_config()`でも取得できます。

検索結果の一部条件がSourceで適用されなかった場合は、`SearchResults.diagnostics`でSourceごとの診断を確認できます。

## `Rhinestone.resolve()`

`Result`または高度な`Config`をResourceへ解決します。

```python
resource = app.resolve(result)
```

## `Resource`

解決済みの具体的なデータです。`uri`、`format`、`media_type`、`metadata`、`provenance`を持ち、Runtimeを明示して開きます。

```python
data = resource.open("rasterio")
```

## `Rhinestone.open()`

Resourceを渡すか、Result/Configを渡して解決とopenを一度に行えます。

```python
data = app.open(result, "rasterio")
```

## `Runtime`

GDAL、Rasterio、pyogrio、RDFLibなど、利用者が所有する外部実行環境です。RDFLibはDCATの検索・解決時に、GDAL、Rasterio、pyogrioは`Resource.open()`時に必要になります。HTTP JSON、HTTP text、JSON serviceは組み込みRuntimeを使用します。インストール例と検証済み範囲は[Runtimeの導入ガイド](runtimes.md)を参照してください。

## 高度なモデル

`Config`、`Source`、`ResourceCandidate`、`AccessPlan`、`FileAccessPlan`、`RemoteDatasetPlan`、`ServiceQueryPlan`、`SearchQuery`、`SearchResult`は内部パイプラインまたは拡張向けです。通常の利用では`Catalog`、`Provider`、`Result`、`Resource`だけを使います。

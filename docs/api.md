# APIリファレンス

このページは、通常の利用で使う公開APIを説明します。初めて使う場合は先に[はじめに](getting-started.md)を読んでください。
用語は[用語と概念](concepts.md)、Adapterを追加する場合は[Source Adapter](api/source-adapters.md)と
[Execution Adapter](api/execution-adapters.md)を参照してください。履歴資料の`architecture/`は現行APIの規範ではありません。

## `Catalog`（提供元の一覧）

データ提供元の設定をまとめた、変更されない一覧です。組み込みCatalogは`rhinestone.catalogs.BUILTIN`です。

```python
from rhinestone.catalogs import BUILTIN
```

## `Provider`（データ提供元）

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

## `configure()`（アプリケーションを作る）

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
| `dependencies` | 利用者が所有するSource / Execution Runtime実体、または明示的な`RuntimeFactory`。公開引数は共通だが内部では利用段階ごとに分離される |
| `credentials` | 認証情報を取得するfactory |
| `network_policy` | 宛先制限。`none` または `credentialed`（既定） |
| `adapters` | `SourceAdapterDefinition`／`ExecutionAdapterDefinition`／`KnowledgeAdapterDefinition` の iterable。組み込みは自動登録され、独自定義だけを指定する |

通常のコードでは`catalog`を使ってください。`sources`はCatalogを使わない互換・高度な指定として利用できます。
遅延Runtimeは `RuntimeFactory(factory)` として指定します。bare valueはcallableでもRuntime
実体として扱われます。`RuntimeFactory`は`configure()`では評価されません。Source Runtimeは検索・解決時、
Execution Runtimeは`Resource.open()`時に、それぞれ初めて必要になった段階で評価されます。

Provider の `settings` に `credential` を論理名として指定すると、CKAN、STAC、OGC
などの HTTP Source へ Credential factory を遅延注入できます。secret 自体は
Provider、Catalog、Result、Resource には保存されません。`credentialed` では、factory の
評価前に Catalog 由来の endpoint へ送信できることを検証します。

## `Rhinestone.search()`（データを検索する）

Catalogに構成されたProvider内のデータ候補を検索し、Resultを返します。Provider自体を発見するAPIではありません。

```python
results = app.search(text="河川", limit=10)
result = results[0]
```

`text`、`bbox`、`time`、`limit`をキーワードで指定できます。`SearchQuery`を渡す形式は高度なAPIです。

`SearchResults`のiterationと整数indexingは、構成したProvider順にgroupを連結し、
各Provider内の順序を保持します。このsequenceは決定的な走査用であり、Providerを
横断した関連度rankingではありません。Provider固有のrankingを扱う場合は
`results.items()`または`results["provider-id"]`でgroupごとに参照します。

## `Result`（検索結果）

検索で見つかった候補です。通常は次のようにResourceへ解決します。

```python
resource = app.resolve(result)
```

`title`、`description`、`discovered_by`、`target`、`metadata`、`provenance`を参照できます。`target`は解決先の`Config`で、`to_config()`でも取得できます。

検索結果の一部条件がSourceで適用されなかった場合や、必須条件不足でSourceがskipされた場合は、`SearchResults.diagnostics`でSourceごとの診断を確認できます。`reason`と`missing_conditions`も参照できます。Providerの通信・metadata・response障害は`reason="provider_failure"`、`failure_type`（`metadata`または`response`）として診断され、他のSourceの結果は継続して返されます。予期しないプログラムエラーはこの診断へ変換されません。

## `Rhinestone.resolve()`（Resourceを確定する）

`Result`または高度な`Config`をResourceへ解決します。

```python
resource = app.resolve(result)
```

## `Resource`（利用するデータ）

解決済みの具体的なデータです。`uri`、`format`、`media_type`、`metadata`、`provenance`を持ち、Runtimeを明示して開きます。

```python
data = resource.open("rasterio")
```

## 形式名の共通定義

Source Adapter 間で共有する format 名と media type 対応は
`rhinestone.representations` から利用できます。

```python
from rhinestone import canonical_format, format_from_media_type

assert canonical_format("GeoPackage") == "gpkg"
assert format_from_media_type("image/tiff") == "geotiff"
```

format の alias と既知の media type だけを正規化し、URL の拡張子から format は推測しません。
`FORMAT_ALIASES`、`MEDIA_TYPE_FORMATS`、`FORMAT_CATEGORIES` は共有定義です。
Execution Adapter がどの format を実行できるかは、各 Adapter の capability として管理されます。

## `Rhinestone.open()`（データを開く）

Resourceを渡すか、Result/Configを渡して解決とopenを一度に行えます。

```python
data = app.open(result, "rasterio")
```

## `Runtime`（外部ライブラリ）

GDAL、Rasterio、pyogrio、RDFLibなど、利用者が所有する外部実行環境です。RDFLibはDCATの検索・解決時に、GDAL、Rasterio、pyogrioは`Resource.open()`時に必要になります。HTTP JSON、HTTP text、JSON serviceは組み込みRuntimeを使用します。インストール例と検証済み範囲は[Runtimeの導入ガイド](runtimes.md)を参照してください。

## 高度なモデル

`Config`、`Source`、`ResourceCandidate`、`AccessPlan`、`FileAccessPlan`、`RemoteDatasetPlan`、`ServiceQueryPlan`、`SearchQuery`、`SearchResult`は内部パイプラインまたは拡張向けです。通常の利用では`Catalog`、`Provider`、`Result`、`Resource`だけを使います。

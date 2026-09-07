# 用語と概念

Rhinestoneの公開メンタルモデルは次のとおりです。

```text
Catalog -> Provider -> Result -> Resource
```

## Catalog

`Catalog`は、Rhinestoneが知っているProviderの集合です。組み込みProviderと利用者が追加するProviderを同じモデルで扱います。

```python
from rhinestone.catalogs import BUILTIN

app = configure(catalog=BUILTIN)
```

`BUILTIN`はリポジトリ管理のCatalogです。`rhinestone.sources`は組み込みProviderを名前で参照するための互換facadeであり、通常の中心概念ではありません。

## Provider

`Provider`はデータを提供する主体・サービスです。endpointやサービス固有の固定知識を持ち、Catalogからアプリケーションへ選択されます。

Providerは、以前の実装で`SourceDefinition`が担っていた「利用する提供元の定義」に相当します。`Source`とは異なり、公開APIではProviderを使います。

## Result

`Result`は検索で見つかった候補です。発見元と、解決先の`Config`、metadata、provenanceを持ちます。

```python
result = app.search(text="河川")[0]
resource = app.resolve(result)
```

`result.discovered_by`は検索を実行したSource ID、`result.target`は通常の解決フローへ渡す`Config`です。この2つは異なっていてよく、横断カタログが別のproviderのresourceを発見するケースを表現できます。

`SearchQuery`、`SearchResult`、`to_config()`は高度な内部パイプラインを扱うための名前です。通常の利用では検索パラメータと`Result`だけを使います。

## Resource

`Resource`は解決済みの具体的なデータです。URI、format、metadata、provenance、アクセス方法を保持し、`open()`でRuntimeへ渡せます。

## Runtime

Runtimeは、Rhinestoneが外部実行に利用する利用者所有の環境です。GDAL、Rasterio、pyogrio、RDFLibなどが該当します。以前の文書で使っていたdependencyやruntime dependencyという表記は、利用者向けにはRuntimeへ統一します。

## Credential

CredentialはAPI keyやtokenなどのsecretです。ProviderやResultへ埋め込まず、アプリケーション構成時にfactoryとして渡します。

## 内部概念

内部では、ProviderをAdapterが解釈して`Source`を作り、`Resolver`が候補から`AccessPlan`と`Resource`を決定します。`Config`、`ResourceCandidate`、Resolver、AccessPlan、Execution Adapter Selector、Registryは責務分離のための内部概念です。

```text
Provider
  -> internal Config
  -> Source
  -> Resolver
  -> internal AccessPlan
  -> Resource
```

これらは拡張やアーキテクチャの文書では必要ですが、通常ユーザーが最初に覚える概念ではありません。

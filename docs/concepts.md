# 用語と概念

Rhinestoneの公開メンタルモデルは次のとおりです。

```text
Catalog -> Provider -> Result -> Resource
```

## 最初に覚える4つの言葉

### Catalog（一覧）

`Catalog`は、Rhinestoneが使う提供元の一覧です。組み込みの一覧と、利用者が追加する提供元を同じ形で扱います。

```python
from rhinestone.catalogs import BUILTIN

app = configure(catalog=BUILTIN)
```

`BUILTIN`はリポジトリ管理のCatalogです。`rhinestone.sources`は組み込みProviderを名前で参照するための互換facadeであり、通常の中心概念ではありません。

### Provider（提供元）

`Provider`はデータを提供するサービスや組織です。接続先やサービス固有の設定を持ち、`Catalog`から選びます。

Providerは、以前の実装で`SourceDefinition`が担っていた「利用する提供元の定義」に相当します。`Source`とは異なり、公開APIではProviderを使います。

### Result（検索結果）

`Result`は検索で見つかったデータ候補です。タイトルなどの表示情報と、次に解決するための情報を持ちます。

```python
result = app.search(text="河川")[0]
resource = app.resolve(result)
```

`result.discovered_by`や`result.target`は高度な情報です。提供元をまたいで検索する場合に、検索した場所と実際のデータの場所が異なることを表します。

`SearchQuery`、`SearchResult`、`to_config()`は高度な内部パイプラインを扱うための名前です。通常の利用では検索パラメータと`Result`だけを使います。

### Resource（利用するデータ）

`Resource`は、URI、形式、メタデータ、アクセス方法が確定したデータです。`open()`でGDALやRasterioなどへ渡せます。

### Runtime（外部ライブラリ）

Runtimeは、Rhinestoneが処理を任せる利用者所有の外部ライブラリです。GDAL、Rasterio、pyogrio、RDFLibなどが該当します。必要になるまで読み込まない場合は`RuntimeFactory`を使います。

### Credential（認証情報）

CredentialはAPI keyやtokenなどの秘密情報です。ProviderやResultへ埋め込まず、アプリケーション構成時にfactoryとして渡します。

## 内部の仕組み

内部では、ProviderをAdapterが解釈して`Source`を作り、`Resolver`が候補から`AccessPlan`と`Resource`を決定します。`Config`、`ResourceCandidate`、Resolver、AccessPlan、Execution Adapter Selector、Registryは責務分離のための内部概念です。

```text
Provider
  -> internal Config
  -> Source
  -> Resolver
  -> internal AccessPlan
  -> Resource
```

これらはAdapterを追加する場合などに必要ですが、通常の利用では意識する必要はありません。

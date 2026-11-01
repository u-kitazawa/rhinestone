# 外部ライブラリ依存方針

Rhinestoneは、配信元・プロトコル固有の解釈を必要な範囲で担当し、データの読み込みや変換は専門ライブラリへ委譲します。外部ライブラリを追加するかどうかは、単にAPIを呼び出せるかではなく、Rhinestoneが自前で意味論を再実装することになるかで判断します。

## 依存境界

| 層 | Rhinestoneの方針 | 例 |
| --- | --- | --- |
| Core | 軽量な必須依存だけを持つ | `jsonschema`、`pystac-core`（標準STAC文書・リンク解釈） |
| HTTP通信 | 組み込みで提供する | 提供元メタデータ、JSONサービス |
| Provider Adapter | 提供元／通信仕様の解釈を担当する。専用ライブラリは意味の委譲が必要な場合だけ採用する | STAC、DCAT |
| Runtime Adapter | 選択済みAccessPlanを専門ライブラリの呼び出しへ翻訳する | GDAL、Rasterio、pyogrio |
| Runtime | Providerは構成時、Runtimeは`open()`時に利用者が供給する | `gdal`、`rasterio`、`pyogrio`、`rdflib` |

CoreはGDAL、Rasterio、pyogrio、RDFLibなどを直接importしません。HTTP通信も公開APIでtransportを注入させず、Rhinestoneの組み込みtransportを使います。

Runtimeの導入例と、実際にAdapterを実行して確認したバージョンは[Runtimeの導入ガイド](runtimes.md)に記載します。そこにある`tested`は検証済み範囲であり、`pyproject.toml`のdependency constraint、`uv.lock`の再現範囲、または将来の互換性保証を意味しません。

`configure(dependencies=...)`はProvider依存ライブラリだけを受け付けます。遅延評価には`RuntimeFactory`を明示します。Runtimeは`open(..., runtime=...)`で実体を渡します。

- Provider依存ライブラリはprovider / protocol metadataの解釈に必要で、対象Provider Adapterの`search()`または`load()`で初めて必要になった時に評価します。現行例はDCATの`rdflib`です。
- Runtimeは解決済みResourceを開く時に明示的に渡します。現行例は`gdal`、`rasterio`、`pyogrio`です。

## Providerごとの判断

| Provider | 候補ライブラリ | 判断 | 適用する境界 |
| --- | --- | --- | --- |
| DCAT | `rdflib` | RDFの解釈に必要なProvider依存ライブラリとして利用する。依存は利用者から供給し、DCATの`search()`または`load()`で遅延評価する | DCAT Provider Adapter |
| STAC | `pystac-client` / `pystac` | 現在の範囲では組み込みHTTP adapterを維持する。conformance、pagination、filter、asset semanticsの実装が必要になった時に採用を再検討する | 将来のSTAC Provider Adapter |
| PLATEAU | `plateaukit` | CityGMLの意味論を委譲できるか、dataset install lifecycleを持ち込まずに使えるかをPoCで確認するまで採用しない | PoC後にProviderまたはRuntimeの境界を決定 |
| CKAN / GEOSPATIAL_JP | `ckanapi` | 現状の`package_search`、`package_show`、`resource_show`には導入しない。Action API固有処理が増えた場合に再検討する | 現行CKAN Provider Adapter |
| GSI Fundamental | GDAL / pyogrio | 専用GSIライブラリは作らず、GML Resourceを既存Runtime Adapterへ渡す | GML Runtime Adapter |
| GSI XYZ tiles | `mercantile` / `morecantile` | 静的なURL template、XYZ、CRS、zoom rangeで足りる間は導入しない。bboxからtile選択まで担当する場合に再検討する | Static Provider + GDAL Runtime Adapter |
| ODPT | `python-odpt` | 現状はgeneric JSON serviceで足りるため見送る。ODPT固有model interpretationが増えた場合に再検討する | JsonService Runtime Adapter |
| OGC API Features | `OWSLib` | 現行adapterを維持する。Coreの対応範囲を超えるprotocol処理が増えた場合に、Python version互換性を確認して再検討する | OGC API Features Provider Adapter |

この表の「再検討」は依存追加を自動的に意味しません。候補ライブラリが、現在のResource / AccessPlanの境界へ直接適合すること、保守状況とlicenseがプロジェクト方針に適合すること、既存機能を単に二重実装しないことを確認します。

## Provider AdapterとRuntime Adapter

Provider Adapterは、検索・metadata取得・provider固有identifier・queryなど、Resourceを解決するための知識を担当します。Provider依存ライブラリが必要な場合は、この段階で専用runtimeへprotocol semanticsの解釈を委譲します。Runtime Adapterは、選択済みAccessPlanをGDALやRasterioなどの呼び出しへ翻訳します。Runtime AdapterはResourceを選択せず、format変換や解析も行いません。

```text
Provider Adapter
  -> provider / protocol metadata
  -> optional Provider依存ライブラリ
  -> Resource + AccessPlan

Runtime Adapter
  -> selected AccessPlan
  -> Runtime
  -> native object
```

`search()`または`load()`が生成するResourceとAccessPlanは、Provider依存ライブラリの実体・factoryやCredential secretを保持しません。Credentialの論理名とsecretは区別します。AccessPlanの実行はProvider依存ライブラリを必要とせず、`open()`で明示したRuntime AdapterとRuntimeを使って専門ライブラリのnative objectを返します。Rhinestone独自のDataFrameや統計モデルへ強制変換しません。

## Adapter identityとRuntime identity

Runtime Adapterのidentityと、実行に必要なRuntimeのidentityは概念上分離します。

```text
Runtime Adapter identity = どの翻訳規則を使うか
Runtime identity           = どの外部実行環境を呼び出すか
```

現行の組み込みRuntime Adapterは1つのAdapterと1つのRuntimeが対応します。
`RuntimeAdapter.name`は`open()`で明示する選択名で、Runtime実体は同じ呼び出しの
`runtime=`へ渡します。RuntimeをDependency Registryへ登録する契約はありません。
`json-service`だけはCoreがRuntimeを用意するため、`runtime=`を省略します。

## Adapterの連結

Runtime Adapterのchainは導入しません。1つのRuntime Adapterが、必要なrequest、pagination、decodeなどを内部で行い、1つの解決済みResourceを1つの専門runtimeへ渡します。

複数の専門ライブラリを組み合わせる必要が出た場合も、まずprovider / format固有の意味論を1つのAdapter内に閉じ込めます。Adapter間でResourceを暗黙に変換する仕組みは、責務と失敗原因を不明瞭にするため採用しません。

## 採用判断のチェックリスト

新しい外部ライブラリを採用する前に、次を確認します。

1. 自前実装ではprovider / protocol固有の意味論を抱えることになるか。
2. 解決済みResourceをnative objectへ渡す、またはprotocol semanticsを解釈する責務を委譲できるか。
3. Provider / Runtimeのどの段階で必要かを明示し、不要なruntimeをロードせずに済むか。
4. Python version、license、保守状況がプロジェクト方針に適合するか。
5. Provider AdapterとRuntime Adapterのどちらに属するか説明できるか。
6. 既存のgeneric adapterで十分な処理を専用依存へ置き換えていないか。

この方針により、Rhinestoneはcatalog clientやreader frameworkを無条件に内包せず、日本のデータ提供方式を解釈して既存の専門runtimeへ接続する責務に集中します。

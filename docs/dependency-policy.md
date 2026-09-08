# 外部ライブラリ依存方針

Rhinestoneは、配信元・プロトコル固有の解釈を必要な範囲で担当し、データの読み込みや変換は専門ライブラリへ委譲します。外部ライブラリを追加するかどうかは、単にAPIを呼び出せるかではなく、Rhinestoneが自前で意味論を再実装することになるかで判断します。

## 依存境界

| 層 | Rhinestoneの方針 | 例 |
| --- | --- | --- |
| Core | 軽量な必須依存だけを持つ | `jsonschema` |
| HTTP transport | 組み込みで提供する | provider metadata、JSON service |
| Source Adapter | provider / protocolの解釈を担当する。専用ライブラリは意味論の委譲が必要な場合だけ採用する | e-Stat、STAC、DCAT |
| Execution Adapter | 解決済みResourceを専門runtimeの呼び出しへ翻訳する | GDAL、Rasterio、pyogrio |
| Runtime | 利用者が実体またはfactoryとして供給する | `gdal`、`rasterio`、`pyogrio`、`rdflib` |

CoreはGDAL、Rasterio、pyogrio、RDFLibなどを直接importしません。HTTP通信も公開APIでtransportを注入させず、Rhinestoneの組み込みtransportを使います。

公開APIではSource RuntimeとExecution Runtimeを単一の`dependencies`引数で受け取り、Composition Rootが内部Registryへ分離して注入します。`configure()`はどちらのfactoryも評価しません。

- Source Runtimeはprovider / protocol metadataの解釈に必要で、対象Sourceの`search()`または`resolve()`で初めて必要になった時に評価します。現行例はDCATの`rdflib`です。
- Execution Runtimeは解決済みResourceをnative objectとして開くために必要で、`Resource.open()`で初めて評価します。現行例は`gdal`、`rasterio`、`pyogrio`です。

## Sourceごとの判断

| Source | 候補ライブラリ | 判断 | 適用する境界 |
| --- | --- | --- | --- |
| e-Stat | `pyestat` | Source Adapterには導入しない。`resolve()`は組み込みHTTPでmetadata、`statsDataId`、queryを解決する。`open()`の専門runtimeが必要になった時点で採用を検証する | 将来のe-Stat Execution Adapter / `pyestat` runtime |
| DCAT | `rdflib` | RDFの解釈に必要なSource Runtimeとして利用する。依存は利用者から供給し、DCATの`search()`または`resolve()`で遅延評価する | DCAT Source Adapter |
| STAC | `pystac-client` / `pystac` | 現在の範囲では組み込みHTTP adapterを維持する。conformance、pagination、filter、asset semanticsの実装が必要になった時に採用を再検討する | 将来のSTAC Source Adapter |
| PLATEAU | `plateaukit` | CityGMLの意味論を委譲できるか、dataset install lifecycleを持ち込まずに使えるかをPoCで確認するまで採用しない | PoC後にSourceまたはExecutionの境界を決定 |
| CKAN / GEOSPATIAL_JP | `ckanapi` | 現状の`package_search`、`package_show`、`resource_show`には導入しない。Action API固有処理が増えた場合に再検討する | 現行CKAN Source Adapter |
| GSI Fundamental | GDAL / pyogrio | 専用GSIライブラリは作らず、GML Resourceを既存Execution Adapterへ渡す | GML Execution Adapter |
| GSI XYZ tiles | `mercantile` / `morecantile` | 静的なURL template、XYZ、CRS、zoom rangeで足りる間は導入しない。bboxからtile選択まで担当する場合に再検討する | Static Source + GDAL Execution Adapter |
| ODPT | `python-odpt` | 現状はgeneric JSON serviceで足りるため見送る。ODPT固有model interpretationが増えた場合に再検討する | JsonService Execution Adapter |
| OGC API Features | `OWSLib` | 現行adapterを維持する。Coreの対応範囲を超えるprotocol処理が増えた場合に、Python version互換性を確認して再検討する | OGC API Features Source Adapter |

この表の「再検討」は依存追加を自動的に意味しません。候補ライブラリが、現在のResource / AccessPlanの境界へ直接適合すること、保守状況とlicenseがプロジェクト方針に適合すること、既存機能を単に二重実装しないことを確認します。

## Source AdapterとExecution Adapter

Source Adapterは、検索・metadata取得・provider固有identifier・queryなど、Resourceを解決するための知識を担当します。Source Runtimeが必要な場合は、この段階で専用runtimeへprotocol semanticsの解釈を委譲します。Execution Adapterは、選択済みResourceをGDALやRasterioなどの呼び出しへ翻訳します。Execution AdapterはResourceを選択せず、format変換や解析も行いません。

```text
Source Adapter
  -> provider / protocol metadata
  -> optional Source Runtime
  -> Resource + AccessPlan

Execution Adapter
  -> selected Resource
  -> Execution Runtime
  -> native object
```

`resolve()`が返すResourceとAccessPlanは、Source Runtimeの実体・factoryやcredentialを保持しません。Resourceのopen経路はExecution Runtimeだけを参照します。`open()`が必要なExecution AdapterとRuntimeを解決し、専門ライブラリのnative objectを返します。Rhinestone独自のDataFrameや統計モデルへ強制変換しません。

## Adapter identityとRuntime identity

Execution Adapterのidentityと、実行に必要なRuntimeのidentityは概念上分離します。

```text
Execution Adapter identity = どの翻訳規則を使うか
Runtime identity           = どの外部実行環境を呼び出すか
```

現行の組み込みAdapterは1つのAdapterと1つのRuntimeが対応するため、`ExecutionAdapter.name`を選択名とDependency Registryのキーに兼用します。これは現在の契約として維持します。

将来、e-Statのように`estat` Adapterが`pyestat` Runtimeを使うケースを追加する場合は、Adapter選択名とruntime dependency名を別フィールドへ分離します。その変更までは、未使用の`runtime_name`を先行導入せず、既存の`name`契約を増やしません。

## Adapter chain

Execution Adapterのchainは導入しません。1つのExecution Adapterが、必要なrequest、pagination、decodeなどを内部で行い、1つの解決済みResourceを1つの専門runtimeへ渡します。

複数の専門ライブラリを組み合わせる必要が出た場合も、まずprovider / format固有の意味論を1つのAdapter内に閉じ込めます。Adapter間でResourceを暗黙に変換する仕組みは、責務と失敗原因を不明瞭にするため採用しません。

## 採用判断のチェックリスト

新しい外部ライブラリを採用する前に、次を確認します。

1. 自前実装ではprovider / protocol固有の意味論を抱えることになるか。
2. 解決済みResourceをnative objectへ渡す、またはprotocol semanticsを解釈する責務を委譲できるか。
3. Source / Executionのどの段階で必要かを明示し、不要なruntimeをロードせずに済むか。
4. Python version、license、保守状況がプロジェクト方針に適合するか。
5. Source AdapterとExecution Adapterのどちらに属するか説明できるか。
6. 既存のgeneric adapterで十分な処理を専用依存へ置き換えていないか。

この方針により、Rhinestoneはcatalog clientやreader frameworkを無条件に内包せず、日本のデータ提供方式を解釈して既存の専門runtimeへ接続する責務に集中します。

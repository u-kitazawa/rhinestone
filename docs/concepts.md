# 用語と概念

通常の流れは `search → Resource → open → Data` です。

## CatalogとProvider

`Catalog`は構成するProviderの一覧です。`Provider`は接続先やサービス固有の設定を持ちます。
標準構成は`search()`から利用でき、`providers=[ProviderId.GSI]`のように検索対象を限定できます。
独自の接続先・認証・Adapterを使う場合は`configure()`を使います。

## ResourceとReference

検索は配信単位の`Resource`を返します。Datasetの複数の配信は別々のResourceになります。
ResourceはURI、形式、metadata、provenance、Reference、任意のAccessPlanを保持します。
`Reference`はProvider、Dataset、配信単位を識別する非秘密の値です。
既知の対象は`app.load(reference)`で直接読み込めます。

発見した場所と配信する場所は同じとは限りません。発見側の記録は`resource.discovery`、
配信対象は`resource.reference`で区別します。target metadataを読み込んでもdiscoveryは保持します。

## AccessPlan

`AccessPlan`は1つの配信を実行するための契約です。形式、配信方式、ZIPやencodingなどの
options、論理credential参照を保持します。検索時点で計画がない場合は、open時に
Referenceから読み込みます。形式が確定しなければ明示的に失敗し、URLから推測しません。

通常は計画を意識する必要はありません。別プロセスで実行する場合だけ
`app.plan(resource) → to_dict() → AccessPlan.from_dict() → receiving_app.open(plan, ...)`
を使います。受信側が自身の宛先制限と認証設定で再検証します。

## RuntimeとCredential

Runtimeは利用者所有の外部ライブラリです。RDFLibなど検索・load用のRuntimeは
`configure(dependencies=...)`、GDAL、Rasterio、pyogrioなど実行用のRuntimeは
`open(..., runtime=...)`へ渡します。
Credentialはsecretを返すfactoryとして構成します。ReferenceやAccessPlanにはsecretを保存しません。

## Adapter

Source AdapterはProvider固有の識別子・配信情報をResourceへ変換します。
Execution AdapterはAccessPlanを解釈して利用者のRuntimeへ渡します。
CoreはProvider固有の候補選択やデータ解析を行いません。

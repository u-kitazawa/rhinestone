# Source Adapter 契約

## 責務

Source Adapter は外部 provider と Core の境界です。Config の provider 固有項目、API request、response schema、resource 構造、format 表現を理解し、Core が扱える Source を生成します。

例として CKAN Adapter は resource identifier、package/resource 構造、resource URL、format、metadata structure を理解します。e-Stat Adapter は statsDataId、統計表 Metadata、dimension、category、area、time、API query を理解します。

## 共通契約

Source Adapter は次を満たさなければなりません。

- 公式の machine-readable interface を使用する（MUST）。
- provider 固有 Reference と response structure を Adapter 内部に閉じ込める（MUST）。
- 解釈済みの共通情報と raw metadata を Source に保持する（MUST）。
- Resource 候補、Capability 情報、Metadata、Provenance を欠落させない（MUST）。
- HTML DOM、CSS selector、XPath、headless browser、HTML regex を使用しない（MUST NOT）。
- download URL や未提示 format を推測しない（MUST NOT）。

公式 API、STAC API、OGC API、DCAT、documented REST/GraphQL API、direct resource URL などの確実なインターフェースがない provider は unsupported とします。

## 組み込み追加 Adapter

`GsiTileAdapter` は同梱した公式由来のタイル定義を Source として扱い、`GdalAdapter` が選択済み XYZ template を GDAL TMS 定義へ翻訳します。URL から tile ID は推測しません。

`PlateauAdapter` は G 空間情報センターの CKAN Action API から distribution を読み、PLATEAU と配布基盤の由来を残します。`GsiFundamentalAdapter` はユーザーが取得済みの基本項目ファイルのみを扱い、ログイン画面や HTML を操作しません。

`DcatAdapter` は利用者が渡す RDF runtime と文書取得 callback で JSON-LD、Turtle、RDF/XML を解釈します。Dataset は Source、`downloadURL` を持つ Distribution は候補になります。`accessURL` だけの landing page は候補にしません。

`OdptAdapter` は ODPT v4 の固定 endpoint、dataset type、公式 filter を検証して ServiceQueryPlan を作ります。`JsonServiceAdapter` が選択済みの Plan を requests 互換 runtime へ渡し、credential factory から得た secret をその直前に `acl:consumerKey` として付与します。

## Search Capability

検索を提供する Adapter だけが search Capability を宣言します。未対応条件を黙って無視せず、結果には Config へ戻るための provider 固有情報、Metadata、Provenance を含めます。

## Adapter Registry

Source Adapter と Execution Adapter の登録状態は内部 Adapter Registry が管理します。
利用者は Adapter instanceを登録しません（MUST NOT）。Composition Rootは
`ProviderConfig.adapter_type`から組み込みSource Adapterを生成し、利用可能なdependency
に対応する組み込みExecution Adapterを構成します。

RegistryはSource Adapter種別ではなく`source_id`でproviderを識別します。同じ
Adapter種別を利用する複数providerを同時に登録できなければなりません（MUST）。
外部拡張機構は反復可能な契約が実例で確認された場合にのみ設計します。

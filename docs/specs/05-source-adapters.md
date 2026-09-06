# Source Adapter 契約

## 責務

Source Adapter は外部 provider または Catalog で管理された静的定義と Core の境界です。Config の provider 固有項目、API request、response schema、resource 構造、format 表現を理解し、Core が扱える Source を生成します。

接続先や公式仕様の固定値は Catalog または利用者が渡す `SourceDefinition.settings` から受け取ります。Adapter のコードへ接続先を埋め込みません。

## 共通契約

Source Adapter は次を満たさなければなりません。

- 公式の machine-readable interface またはレビュー済みの静的定義を使用する（MUST）。
- provider 固有 Reference と response structure を Adapter 内部に閉じ込める（MUST）。
- 解釈済みの共通情報と raw metadata を Source に保持する（MUST）。
- Resource 候補、Capability 情報、Metadata、Provenance を欠落させない（MUST）。
- HTML DOM、CSS selector、XPath、headless browser、HTML regex を使用しない（MUST NOT）。
- download URL や未提示 format を推測しない（MUST NOT）。

公式 API、STAC API、OGC API、DCAT、documented REST/GraphQL API、direct resource URL、レビュー済みの静的定義などの確実なインターフェースがない provider は unsupported とします。

## Catalog loading

`rhinestone.catalogs` が Catalog resource を読み込み、`SourceDefinition` を生成します。`rhinestone.sources` は組み込み定義を公開する facade です。Source Adapter は Catalog のファイル名・パッケージ配置・loader を参照せず、constructor 引数または `SourceDefinition.settings` として宣言値を受け取ります。

この分離により、Catalog を JSON 以外の配布形態へ変更しても、また Adapter を別ライブラリで再利用しても、Adapter の接続コードを変更せずに済みます。

## 組み込み追加 Adapter

`StaticAdapter` はリポジトリまたは利用者が管理する静的なサービス定義を `Source` として扱います。組み込みの国土地理院タイル定義は Catalog から `sources.GSI` へ注入し、`GdalAdapter` が選択済み XYZ template を GDAL TMS 定義へ翻訳します。URL から tile ID は推測しません。

`GsiTileAdapter` はタイル仕様の mapping を constructor から受け取ります。`gsi_tile_specs.json` の読み込みは Catalog loader またはアプリケーションの責務であり、Adapter はリポジトリ構造を知りません。

`PlateauAdapter` は Catalog から渡された G 空間情報センター CKAN endpoint を使って distribution を読み、PLATEAU と配布基盤の由来を残します。`GsiFundamentalAdapter` はユーザーが取得済みの基本項目ファイルのみを扱い、ログイン画面や HTML を操作しません。

`DcatAdapter` は利用者が渡す RDF runtime と文書取得 callback で JSON-LD、Turtle、RDF/XML を解釈します。Dataset は Source、`downloadURL` を持つ Distribution は候補になります。`accessURL` だけの landing page は候補にしません。

`OdptAdapter` は Catalog から渡された v4 endpoint、dataset type、公式 filter を検証して ServiceQueryPlan を作ります。`JsonServiceAdapter` が選択済みの Plan を requests 互換 runtime へ渡し、credential factory から得た secret をその直前に `acl:consumerKey` として付与します。

## Search Capability

検索を提供する Adapter だけが search Capability を宣言します。未対応条件を黙って無視せず、結果には Config へ戻るための provider 固有情報、Metadata、Provenance を含めます。

## Adapter Registry

Source Adapter と Execution Adapter の登録状態は内部 Adapter Registry が管理します。利用者は Adapter instance を登録しません（MUST NOT）。Composition Root は `SourceDefinition.adapter_type` から組み込み Source Adapter を生成し、利用者が供給した dependency に対応する組み込み Execution Adapter を構成します。

Registry は Source Adapter 種別ではなく `source_id` で Source を識別します。同じ Adapter 種別を利用する複数 Source を同時に登録できなければなりません（MUST）。外部拡張機構は反復可能な契約が実例で確認された場合にのみ設計します。

# G空間情報センターの提供元Adapter

`GeospatialJpAdapter`（種別 `geospatial-jp`）はG空間情報センターのCKAN Action APIを使用します。
組み込みProviderのendpointはCatalogで管理し、通信と認証は共通transportに委譲します。
CKANの通信・応答解析・Resource展開は共通clientを使いますが、`CkanAdapter`を継承・呼び出しません。
地域順の探索、地域照合、巡回展開はこのAdapterが所有します。

- Provider設定: `endpoint`、任意のcredential設定。`spatial_search`は受け付けません。
- 直接loadの入力: `Reference("geospatial-jp", parameters={"resource_id": "公式Resource ID"})`を`app.load()`へ渡します。
- 検索入力: `text`、正式区域名の `area`、`format`、`limit`。
- load出力: packageとresourceのmetadataを保持する `Resource`。
- 検索出力: 配信単位の `Resource`。各Resourceの`reference`は同じProviderの`resource_id`を持つ`Reference`です。

検索結果は`app.open(resource, library, runtime=...)`、または検索コンテキストが付いた
`resource.open(library, runtime=...)`で開きます。取得先へ明示的に問い合わせる場合は
`app.load(resource.reference)`を使います。AccessPlanを持つResourceを`app.load(resource)`へ
渡した場合は再問い合わせせず、現在のアプリケーションへbindします。
利用するExecution AdapterとRuntimeは明示して選びます。

本文は空白区切りの各語をタイトル全体（title_string）・タグで部分一致検索し、語同士を明示的ANDで結びます。地域指定時はAPI側のarea・tags条件で
指定地域、含有都道府県、地方、全国の順に検索し、地域無指定の通常検索を混ぜません。
各段階で本文＋地域名のAPI検索も併用し、area・タグで地域一致を照合します。
カンマ区切りの地域metadataを比較し、取得範囲内では本文タグも優先順に使用します。
各DatasetからResourceを巡回して展開し、形式照合後の件数まで必要に応じて追加pageを取得します。
共通の公開契約と他のCKAN Providerの挙動は変更しません。

設定例、入出力、優先順、ページング、実APIで確認済み・未検証の範囲は
[APIリファレンス](../../../../../docs/api/adapters/geospatial-jp.md)を参照してください。

# G空間情報センターの提供元Adapter

`GeospatialJpAdapter`（種別 `geospatial-jp`）はG空間情報センターのCKAN Action APIを使用します。
組み込みProviderのendpointはCatalogで管理し、通信と認証は共通transportに委譲します。

- Provider設定: `endpoint`、任意のcredential設定。`spatial_search`は受け付けません。
- 解決入力: `Config("geospatial-jp", {"resource_id": "公式Resource ID"})`。
- 検索入力: `text`、正式区域名の `area`、`format`、`limit`。
- 解決出力: packageとresourceのmetadataを保持する `Source`。
- 検索出力: Resource単位の `Result`。同じProviderの `resource_id` Configで解決します。

本文は空白区切りの各語をタイトル全体（title_string）・タグで部分一致検索し、語同士を明示的ANDで結びます。地域指定時はAPI側のarea・tags条件で
指定地域、含有都道府県、地方、全国の順に検索し、地域無指定の通常検索を混ぜません。
各段階で本文＋地域名のAPI検索も併用し、area・タグで地域一致を照合します。
カンマ区切りの地域metadataを比較し、取得範囲内では本文タグも優先順に使用します。
各DatasetからResourceを巡回して展開し、形式照合後の件数まで必要に応じて追加pageを取得します。
共通の公開契約と他のCKAN Providerの挙動は変更しません。

設定例、入出力、優先順、ページング、実APIで確認済み・未検証の範囲は
[APIリファレンス](../../../../../docs/api/adapters/geospatial-jp.md)を参照してください。

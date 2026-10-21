# PLATEAUの提供元アダプター

`PlateauAdapter` はG空間情報センターのCKANカタログから、配信単位の`Resource`を生成します。
CKANの通信・ページング・Resource展開は共通clientを使い、`CkanAdapter`を継承・呼び出しません。
PLATEAUタグによる検索範囲と、直接loadでの配信選択・Knowledge付加はこのAdapterが所有します。

- Adapter 種別（`adapter_type`）: `plateau`
- Provider設定: `endpoint`。
- 直接loadの識別子: Referenceの`resource_identifier`または`dataset_identifier`。代わりに`parameters`の`resource_id`または`dataset_id`でも指定でき、重複指定は不要です。
- 任意項目: `format`, `archive: zip`, `entry_point`。選択にはAPIが示す識別子・形式を使います。
- 検索: CKANの`text`, `format`, `limit`。明示的な`PLATEAU`タグで対象Datasetを限定します。
- 注入: `get_json(url, params)`。

直接loadはSource Adapter内で配信を一意に選びます。複数の配信が一致すれば
`AmbiguousResourceError`、一致する配信がなければ`ResourceNotFoundError`です。
先頭配信や市区町村・年度から配布物を暗黙に選びません。

検索はCKANと同様に配信単位のResourceを返し、`limit`は形式照合後のResource数です。
直接loadで`archive="zip"`を指定する場合、安全な相対`entry_point`も必須です。
ZIP内のmemberを探索・推測しません。選択後のAccessPlanをGDAL等へ渡す手順は
[APIリファレンス](../../../../../docs/api/adapters/plateau.md)を参照してください。
設定は [schema.json](schema.json) で補完・構造検証できます。

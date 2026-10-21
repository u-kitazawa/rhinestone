# PlateauAdapter（PLATEAU提供元アダプター）

`PlateauAdapter` は G 空間情報センターの CKAN catalog から PLATEAU 配布物を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `plateau`

## 設定と接続先

直接loadでは配信またはDatasetの識別子を指定します。Referenceの`resource_identifier`、
または`dataset_identifier`を使えます。代わりに`Reference.parameters`の`resource_id`、
または`dataset_id`でも指定でき、同じ識別子を両方へ重複して入れる必要はありません。
Providerの`endpoint`はCatalogから渡され、CKAN Action APIへのHTTP通信は
Rhinestoneの組み込みtransportを使用します。検索条件は`text`、`format`、`limit`です。

`time`をReferenceへ指定する場合は、必要に応じて`time_kind`に`calendar_year`、
`fiscal_year`、`survey_year`、`as_of_date`のいずれかを指定して意味を明示できます。
これは配信に関する知識の付加であり、検索の`time`条件ではありません。

検索ではG空間情報センターがデータセットに付与した明示的な`PLATEAU`タグをCKAN
Action APIの`fq`で指定します。同じendpointを使う`geospatial-jp`はタグで限定せず、
G空間情報センター全体を検索します。endpointの共有は、検索対象が同じことを意味しません。

CKANの通信・応答解析・ページングは共通clientを構成して共有します。
`CkanAdapter`の継承や別Adapterの生成は行わず、PLATEAU固有の検索条件と配信選択を維持します。

Adapterを直接構築する内部テストや再利用用途では、transport callbackをconstructorへ注入できます。標準の`configure()`経路で利用者がHTTP callbackを登録する必要はありません。

## 直接loadでの配信選択

Source Adapterは、指定したresource IDと任意の`format`で配信を絞り、1件のResourceを返します。
dataset指定で複数の配信が一致すれば`AmbiguousResourceError`、一致する配信がなければ
`ResourceNotFoundError`になります。市区町村・年度や先頭順から配布物を推測しません。

`archive="zip"`は任意ですが、直接loadで指定した場合は`entry_point`も必須です。
絶対パス、`..`やバックスラッシュを含むパスなどを拒否し、安全な相対パスだけを受け付けます。
ZIP内を走査してmemberを選ぶことはありません。検索結果を得るだけでZIP memberの
指定や実データ取得の成功が保証されるわけではありません。

CityGML の ZIP member を明示して GDAL で開く例は、リポジトリ checkout の `examples/09_plateau_citygml/README.md` にあります。

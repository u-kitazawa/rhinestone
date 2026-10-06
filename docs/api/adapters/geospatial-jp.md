# GeospatialJpAdapter（G空間情報センター）

[Source Adapter 一覧](../source-adapters.md) · source type: `geospatial-jp`

組み込みProvider `geospatial-jp` は専用Adapterを使用します。
CKANの `resource_show` / `package_show` による解決処理を共有し、検索戦略だけを独立させています。
他のCKAN ProviderとPLATEAU専用Providerの検索挙動は変更しません。

## 設定と入出力

Providerの `endpoint` はCatalogから渡されます。`credential`、`credential_header`、
`credential_scheme` も設定できます。公開検索のためのAPIトークンは通常不要です。
`Config.settings` は `resource_id` が必須で、任意の `endpoint` はProvider設定と一致する必要があります。
`spatial_search` はこのProviderの構成項目ではありません。

検索条件は `text`、`area`、`format`、`limit` です。bboxとtimeは未対応diagnosticになります。
共通処理は `area` をKnowledge Adapterで検証・正規化し、正式区域名として専用Adapterへ渡します。
本文への連結やbboxへの変換は行いません。

結果はResource単位の `Result` です。`target` は同じProviderの `resource_id` Configを指します。
packageとresourceのmetadataは `raw_metadata`、実際の検索APIパラメータは
`provenance.query_parameters` に保持します。解決後の形式とURLはCKANの宣言を使います。

## 検索戦略

`text` は空白（全角空白を含む）で分割し、各語をSolrの引用符付きリテラルとして
明示的な `AND` で結びます。例えば `河川 洪水` は `"河川" AND "洪水"` です。
引用符とバックスラッシュをエスケープします。`OR`、ワイルドカード、field指定を
利用者入力の演算子として解釈しません。空の本文は `q=*:*` になります。

`area` がある場合は次の2経路から候補を取得します。

- 同じ本文条件と `fq=tags:"正式区域名"` による地域タグ検索
- 同じ本文条件だけの通常検索。全国・地方データやタグ未登録のデータも候補に残す

索引fieldとして利用するのは公式資料に例示された `tags` だけです。
未確認の `fq=area`、organization、groups、res_format、独自sortは使いません。

取得した候補は、packageの `area` と `tags[].name` に基づき次の順に並べます。
同じ優先度なら本文語と完全一致するタグ数が多い候補を先にし、それも同じならProviderの応答順を保ちます。

| 優先順 | 地域metadataとの関係 |
| --- | --- |
| 1 | 正式区域名に一致。`都道府県_市区町村` の区切りを正規化する |
| 2 | 市区町村検索に対する都道府県、都道府県検索に対する配下の市区町村 |
| 3 | 対象都道府県を含む地方。北海道・東北・関東・中部・関西・中国・四国・九州の定義をAdapter内で保持する |
| 4 | `全国` または `日本全国` |
| 5 | 地域metadata不足または他地域。除外せず通常検索の候補として残す |

これはmetadata上の関係による候補の優先順であり、データ内の地理的範囲の保証ではありません。
地域名が説明文に出現するだけの候補に地域一致の優先度は与えません。
Provider横断の順位付けは行いません。

## Resource展開とページング

1回の候補取得範囲は各経路の100 Datasetずつです。重複Datasetをまとめてから
上記の優先順を適用し、各Datasetの最初のResource、各Datasetの次のResource、と巡回して展開します。
形式を照合してから巡回するため、不一致Resourceで上位が埋まりません。
Resource IDも検索全体で重複を除きます。

`limit` は形式照合後のResource数です。不足する場合は未終了の経路の次pageを `start` で取得します。
優先順と巡回展開は取得範囲ごとに適用し、後続pageの候補を既に返した候補より前へ移動しません。
全件に対する一括ランキングや全Datasetの事前取得は行いません。
`limit=None` は各経路の最初のpageだけ、`limit=0` は通信なしです。
Providerが1pageで返す件数が100より少なくても、`count` に従って次pageへ進みます。
`count` 不正や宣言件数より前の空pageは応答エラーとして診断されます。

`format` はResourceの宣言済みformatか対応media typeで照合し、URL拡張子から推測しません。
通常のCKANと同じcanonical形式とUNKNOWNの扱いを使います。

## 例

```python
from rhinestone import Config, Format, ProviderId, configure
from rhinestone.catalogs import BUILTIN

app = configure(catalog=BUILTIN)
results = app.search(
    text="河川",
    area="神奈川県",
    format=(Format.GEOJSON,),
    limit=5,
    providers=[ProviderId.GEOSPATIAL_JP],
)
for result in results[ProviderId.GEOSPATIAL_JP]:
    print(result.title, result.provenance.query_parameters)

# resource_idは公式APIで取得した実際のIDに置き換える。
resource = app.resolve(Config(ProviderId.GEOSPATIAL_JP, {"resource_id": "resource-uuid"}))
```

## 検証範囲

[公式API資料](https://front.geospatial.jp/how_to_use/manual8/)に掲載されたAction APIとタグfieldを使用し、
本文は[CKAN Action APIのSolrクエリ契約](https://docs.ckan.org/en/2.11/api/#ckan.logic.action.get.package_search)に従って構築しています。
2026-10-06の実装時点ではこの環境から実APIがHTTP 403となり、
G空間の現在の索引・語分割・検索構文と検索品質の比較はライブ検証できていません。
テストfixtureは合成データと明示し、通常CIは外部APIに依存しません。

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

`area` がある場合は、次の段階を順に検索します。各段階で、本文条件にAPI側の
`area`・`tags` のOR条件を `fq` として加える経路と、本文にその段階の地域名をANDで
加える経路を併用します。地域指定があるときに地域無指定の通常検索を混ぜません。

1. 指定した地域。都道府県指定では、`都道府県_市区町村` のprefix条件も含めます。
2. 市区町村指定の場合、その市区町村を含む都道府県。隣接・同県の別市区町村をprefixで追加しません。
3. 対象都道府県を含む地方（例: 島根県なら `中国` / `中国地方`）。
4. `全国` / `日本全国`。

例えば、島根県の最初の条件は次のとおりです。

```text
q="河川"
fq=(area:"島根県" OR tags:"島根県" OR area:島根県_* OR tags:島根県_*)
```

補完経路は `q="河川" AND "島根県"` です。応答にareaがあってもarea検索に一致せず、
地域タグもないDatasetを地域名付き本文検索で拾います。API側で候補を絞ったうえで、
両経路の応答の `area`・タグがその検索段階の地域関係に一致することを照合します。
説明文に地域名が出るだけの候補や、地域情報不足で一致を確認できない候補は追加しません。
本文に地域名がなく、areaも検索索引に反映されず、地域タグもないDatasetは取得できません。

検索の演算子とprefixはAdapterが組み立てます。利用者の本文はリテラルのままです。
市区町村はProviderの `都道府県_市区町村` 表記と区切りなし表記を検索します。
郡名付きの区域名は、組み込み行政区域snapshotの都道府県付き別名を使います。
例えば `北海道虻田郡ニセコ町` は `北海道_ニセコ町` / `北海道ニセコ町` を検索します。
`郡山市`のような市名から文字を削除したり、都道府県のない別名で他県を一致させたりはしません。

APIから取得したpage内では、packageの `area` と `tags[].name` による地域一致、
本文語と完全一致するタグ数、Providerの応答順で安定して並べます。
`area` にカンマ区切りの複数地域がある場合は、分割して比較します。raw metadataは変更しません。
指定地域、含有都道府県、地方、全国の順は検索段階の順で保証します。
地域に該当するAPI候補がなければ0件となり、他県の通常検索で件数を埋めません。
地域指定がない場合だけ、従来どおり本文による通常検索を行います。

これはDataset metadata上の地域関係であり、各Resourceの地理的範囲の保証ではありません。
複数地域のDatasetから得た個々のResourceが指定地域向けとは断定しません。
Resourceの名前から地域を推測せず、ファイルの内容による空間的な切り出しも行いません。
Provider横断の順位付けは行いません。

## Resource展開とページング

各検索段階で両経路から100 Datasetずつ取得します。取得範囲は最大200 Datasetです。
地域照合と重複排除の後、各Datasetの最初のResource、
各Datasetの次のResource、と巡回して展開します。形式を照合してから巡回するため、
不一致Resourceで上位が埋まりません。Resource IDも検索全体で重複を除きます。

`limit` は形式照合後のResource数です。不足する場合は同じ検索段階の次pageを `start` で取得します。
その段階の両経路が終了しても不足するときだけ、次の広域段階へ進みます。
巡回展開はpageごとで、全Datasetの事前取得や全件の一括ランキングは行いません。
`limit=None` は各段階・各経路の最初のpageだけ、`limit=0` は通信なしです。
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

[公式API資料](https://front.geospatial.jp/how_to_use/manual8/)に掲載されたAction APIを使用します。
2026-10-06にユーザーの環境で `q="河川"&fq=tags:"島根県"` の成功と、
`q="河川"&fq=area:"島根県"` の `success=true, count=5` を確認しました。
実Datasetにカンマ区切りの複数地域が格納されることも確認済みです。
同日ユーザー環境で、三重県の国土数値情報（ダム）は
`q="国土数値" AND "ダム"&fq=area:"三重県"` が0件、
`q="国土数値" AND "ダム" AND "三重県"` は `success=true, count=1` でした。
返されたDatasetに `area="三重県"` があり、タグは `国交DPF` のみ、ResourceはGeoJSONです。
この観測応答の必要項目をfixtureに保存して索引不一致の回帰を検証しています。

OR式と市区町村prefix検索は[CKAN Action APIのSolr契約](https://docs.ckan.org/en/2.11/api/#ckan.logic.action.get.package_search)
に従いますが、G空間の現索引に対する組合せ・prefixの実API検証は未完了です。
この実装環境からの通信はHTTP 403で、修正後の検索品質をライブ比較できていません。
合成fixtureとユーザー提供の観測応答の抜粋を区別し、通常CIは外部APIに依存しません。

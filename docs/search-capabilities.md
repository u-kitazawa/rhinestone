# 検索能力の対照表

この表は現行の `SearchQuery(text, area, bbox, time, format, limit)` が各 Source Adapter でどこまで
適用されるかを示します。検索結果はすべて既存の `Resource` であり、`resolve()` への経路、
discovery provenance、provider ごとの順序は変わりません。

`area`は検索前に行政区域Knowledge Adapterで解決されます。`area`対応Adapterには正式区域名を直接渡し、G空間情報センターでは独立した地域条件、MLIT DPFでは行政コードの属性条件として扱います。STAC、OGC API Featuresと、空間検索を明示的に有効化したCKANにはbboxとして、通常のCKAN、PLATEAU、search.ckan.jp、DCAT、Staticには正式区域名のtextとして投影されます。e-Stat GISでは未対応diagnosticになります。未知区域は全Providerの呼び出し前に失敗します。

| Adapter | 対応条件と適用段階 | ページング / `limit` | 非対応・境界 |
| --- | --- | --- | --- |
| G空間情報センター | `text`は各語をtitle_string・tagsで部分一致（OR）、語同士は明示的AND。入力記号はリテラル。`area`は正式区域名で受け取り、API側のarea・tags条件で指定地域→含有都道府県→地方→全国の順に検索。各段階で本文＋地域名の検索も併用し、area・タグで地域一致を照合。地域無指定の本文検索を混ぜない。カンマ区切り地域metadataを比較。`format`はResourceごとに照合 | 各段階・各経路100 Dataset/pageの取得範囲でResourceを巡回展開。形式照合後のResource数が`limit`に足りなければ同じ段階の次page、両経路終了後は次の広域段階。`limit=None`は各段階・各経路の先頭page | bbox・timeは未対応。全候補の一括ランキングではない。実APIの検索品質は未検証。[詳細](api/adapters/geospatial-jp.md) |
| CKAN | `text` を Action API の `q`、`limit` を `rows` に渡す。`format`はAdapter内でResourceごとに照合する。`spatial_search=True`で`ckanext-spatial`を導入済みのサイトに限り、`bbox`を`ext_bbox`へ渡す | `limit` は形式照合後の Resource 数。先頭 page で足りなければ `start` で続きの package を取得する。`limit=None` は provider の既定 page | 既定ではbbox非対応で`area`は正式区域名のtextに変換。空間検索が有効なら`area`をbboxに変換。`ext_bbox`を無視するサイトでは地理条件を保証できないため、対応確認済みのサイトのみ有効化する。time は未対応 |
| PLATEAU | `text`、`format`、`limit`はCKANと同じ。加えてAction APIの`fq=tags:PLATEAU`で、明示的なPLATEAUタグを持つデータセットへ限定する。検索結果の解決時はPLATEAUの明示選択規則を使う | CKAN と同じ | 組み込み`geospatial-jp`と同じCKAN endpointを使うが、`geospatial-jp`はG空間情報センター全体、`plateau`はPLATEAUタグ付きデータセットが検索対象。タグのない関連データを名称から推測して含めない |
| search.ckan.jp | `text` を Backend API の `q` に渡し、package から形式が明示された直接配布 Resource だけを返す。`format`はAdapter内でResourceごとに照合する | `limit` は形式照合後の Resource 数。`count` を根拠に `start` で後続 package を取得する | `text` は必須。形式不明、landing page のみ、credential 埋込み URL は結果にしない。次 page が必要なのに `count` が不正なら response error。検索サービスの構文は provider 依存 |
| MLIT DPF | `text`はphraseMatch trueを優先し、falseで補充。`area`は都道府県・市区町村コードの属性条件。`bbox`はrectangle。解決可能なcatalog / datasetをattributeFilterで絞り、`format`はResource展開後に照合 | first / size / totalNumberで次ページを取得。最大50レコード/page。`limit`は形式照合後のResource数、Noneは50 Resource | `time`は未対応。Nativeの形式はUNKNOWN。地域コード未宣言の全国版を含む保証はない。実APIの品質比較は未検証。[詳細](api/adapters/mlit-dpf.md) |
| STAC | `bbox`、`time`、`limit` を `/search` に渡し、Item の data asset を Resource として返す | provider の `limit` に従う。next link の追跡はしない | collection は Provider 設定内部の絞り込みで、共通条件ではない。data asset が一意でない Item は失敗として診断される |
| OGC API Features | 設定済み collection の `/items` に `bbox`、`datetime`、`limit` を渡す | provider の `limit` に従う。next link の追跡はしない | collection は Provider 設定で必須。`text` は共通条件ではない |
| DCAT | ローカル RDF graph 上で `text` の全語を title / description に照合する | `limit` は照合後 Dataset 数。文書は検索ごとに一度だけ読み込む | RDF catalog の全件を読むため、大きな remote catalog の索引 API にはならない。bbox / time は未対応 |
| Static | ローカル定義の id / title / description に `text` の全語を照合する | `limit` は照合後 Resource 数。通信はしない | bbox / time は未対応 |
| e-Stat GIS | 利用者が与えた distribution index の id / title / dataset / level に `text` の全語を照合する | `limit` は照合後 Resource 数。通信はしない | `load()` の selector（survey year、region など）は検索条件に昇格しない。共通の形式検索は下記の制限がある。UI の HTML は検索しない |

## 形式検索の適用段階

`format`は`Format`または`FormatPreset`の空でないtupleで指定し、複数の形式をOR条件で
照合します。文字列やlistは受け付けません。具体例は[データを検索する](search.md)を参照してください。

| Adapter | 形式を絞り込む場所 | 検索時に照合できる形式 |
| --- | --- | --- |
| G空間情報センター / CKAN / PLATEAU / search.ckan.jp | Adapter内。照合後も必要に応じてpackageの次pageを取得する | 対象Resourceの宣言済みformatまたは対応media type。隣接Resourceの形式は使わない |
| STAC | Search Coordinatorが取得済み結果を絞り込む | 選択済みdata assetの対応media typeから得られる形式 |
| OGC API Features | Search Coordinatorが取得済み結果を絞り込む | `ogc-api-features` |
| Static | Search Coordinatorが取得済み結果を絞り込む | 静的定義の候補に明示されたformat |
| MLIT DPF | Adapter内。必要件数まで次pageを取得する | Directは明示representation。Native委譲は不明として扱う |
| DCAT / e-Stat GIS | Search Coordinatorが取得済み結果を絞り込む | 現行Adapterは`Resource.formats`を設定しないため、形式検索では不明として扱う |

Search Coordinatorで絞り込む場合、Adapterへは`format`を渡さず、`limit=None`で取得した
結果を形式照合してからProviderごとに`limit`を適用します。取得範囲は各Adapterが
`limit=None`で返す範囲です。STAC・OGC等は既定page、ローカル定義の照合は全候補が
対象となり、指定件数に達するまで追加取得する契約ではありません。
CKAN系の形式照合もサーバーの形式検索パラメータへ変換せず、Adapter内で行います。

`Format.UNKNOWN`の照合対象は適用段階によって異なります。

| 適用段階 | `Format.UNKNOWN`に一致する形式集合 | 非空の未登録形式（例：`xlsx`） |
| --- | --- | --- |
| Search Coordinator | 空の集合、`Format`の値へ正規化できない形式だけの集合、または`unknown`を含む集合 | 不明として一致する |
| G空間情報センター / CKAN / PLATEAU / search.ckan.jpのAdapter内 | 空の集合、または`unknown`を明示的に含む集合 | 一致しない |

`canonical_format("XLSX")`は`"xlsx"`を保持し、`None`や`"unknown"`へ変換しません。
CKAN系でこのような未登録形式を取得する場合は`format`を省略して検索し、
`result.formats`を確認してください。形式条件を省略すれば、未知形式だけを抽出する検索には
なりませんが、非空の未登録形式も結果に含まれます。

URIの拡張子やraw metadataを調べて形式を補完したり、検索中に`resolve()`したりしません。
`Format.UNKNOWN`は解決・openの成功を保証せず、Adapterが検索結果自体を省略する規則も
変更しません。たとえばsearch.ckan.jpが省略する形式未宣言のResourceは取得できません。
`FormatPreset.PYOGRIO`も検索候補の形式集合であり、Runtimeのdriver対応を保証しません。

検索しない Direct、基盤地図情報、ODPT などの Adapter はこの表の対象外です。Source が条件を
受け取れないときは、`SearchResults.diagnostics`に条件名と理由を残し、対応する条件だけで
検索します。対応する条件が一つもないSourceや、必須条件が不足するSourceはスキップします。
`format`はCoordinator側でも適用できるため、形式条件だけでも検索できますが、
search.ckan.jpの必須`text`条件は省略できません。

# 検索能力の対照表

この表は現行の `SearchQuery(text, area, bbox, time, limit)` が各 Source Adapter でどこまで
適用されるかを示します。検索結果はすべて既存の `Result` であり、`resolve()` への経路、
discovery provenance、provider ごとの順序は変わりません。

| `area`は検索前に行政区域Knowledge Adapterで解決されます。STAC、OGC API Features、MLIT DPFにはbboxとして、CKAN、PLATEAU、search.ckan.jp、DCAT、Staticには正式区域名のtextとして投影されます。e-Stat GISでは未対応diagnosticになります。未知区域は全Providerの呼び出し前に失敗します。 |

| Adapter | 対応条件と適用段階 | ページング / `limit` | 非対応・境界 |
| --- | --- | --- | --- |
| CKAN | `text` を Action API の `q`、`limit` を `rows` に渡し、package を Resource へ展開する | `limit` は展開後 Resource 数。先頭 page で足りなければ `start` で続きの package を取得する。`limit=None` は provider の既定 page | `q` の AND / phrase / partial match は CKAN 実装の意味。bbox / time / format は共通条件ではない。次 page が必要なのに `count` が不正なら response error |
| PLATEAU | CKAN と同じ検索能力。検索結果の解決時は PLATEAU の明示選択規則を使う | CKAN と同じ | 組み込み `geospatial-jp` と同じ CKAN endpoint を使う。両方を構成すると同じ catalog の結果が別 provider group に現れ得るため、必要な方だけを構成する |
| search.ckan.jp | `text` を Backend API の `q` に渡し、package から形式が明示された直接配布 Resource だけを返す | `limit` は展開後 Resource 数。`count` を根拠に `start` で後続 package を取得する | `text` は必須。形式不明、landing page のみ、credential 埋込み URL は結果にしない。次 page が必要なのに `count` が不正なら response error。検索サービスの構文は provider 依存 |
| MLIT DPF | `text`（phraseMatch を含む）、`bbox`、`limit` を GraphQL 検索へ渡す | `limit` は GraphQL レコード取得数と展開後 Resource 数の上限 | `time` は未対応 diagnostic。明示 target rule または representation がない record は安全に欠落する。詳細 metadata を推測して補完しない |
| STAC | `bbox`、`time`、`limit` を `/search` に渡し、Item の data asset を Resource として返す | provider の `limit` に従う。next link の追跡はしない | collection は Provider 設定内部の絞り込みで、共通条件ではない。data asset が一意でない Item は失敗として診断される |
| OGC API Features | 設定済み collection の `/items` に `bbox`、`datetime`、`limit` を渡す | provider の `limit` に従う。next link の追跡はしない | collection は Provider 設定で必須。`text` は共通条件ではない |
| DCAT | ローカル RDF graph 上で `text` の全語を title / description に照合する | `limit` は照合後 Dataset 数。文書は検索ごとに一度だけ読み込む | RDF catalog の全件を読むため、大きな remote catalog の索引 API にはならない。bbox / time は未対応 |
| Static | ローカル定義の id / title / description に `text` の全語を照合する | `limit` は照合後 Result 数。通信はしない | bbox / time は未対応 |
| e-Stat GIS | 利用者が与えた distribution index の id / title / dataset / level に `text` の全語を照合する | `limit` は照合後 Resource 数。通信はしない | `load()` の selector（format、survey year、region など）は検索条件に昇格しない。UI の HTML は検索しない |

検索しない Direct、基盤地図情報、ODPT などの Adapter はこの表の対象外です。Source が条件を
受け取れないとき、federated search はその Source だけをスキップし、
`SearchResults.diagnostics` に条件名と理由を残します。対応する条件が一つもない Source へ
空検索を送ることはありません。

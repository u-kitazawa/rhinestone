# 横断CKAN検索のサービス仕様に基づく改善

調査日: 2026-10-07（日本時間）。対象: [Issue #185](https://github.com/u-kitazawa/rhinestone/issues/185)。
起点のdevelop: `a7e69ce`。現行の検索契約は[APIリファレンス](../api/adapters/search-ckan-jp.md)を参照してください。

## 調査の進め方

G空間のクエリを転用せず、search.ckan.jpの公式仕様を読む、実APIでfieldと構文を比較する、
検索結果のDatasetとResourceを確認する、観測metadataでテストする、という順で進めました。
対象は標準Catalogの横断検索 `search-ckan-jp` です。
汎用 `CkanAdapter`、G空間、PLATEAU、Coordinator、公開モデルの変更はありません。

## 公式仕様と実APIの区別

根拠はサービスの[APIリファレンス](https://search.ckan.jp/api)と、そこから参照される
[Solr Standard Query Parser](https://solr.apache.org/guide/8_11/the-standard-query-parser.html)です。
API仕様書の版日は2022-02-22ですが、下記の応答は調査日に認証なしGETで観測しました。

| 項目 | 公式仕様 | 実APIの観測と採用判断 |
| --- | --- | --- |
| 通常の本文検索 | 日本語を単語分割し、一部の語だけでも検索する | 複数語は引用した語の明示的ANDに変更 |
| 検索構文 | Standard Query Parser。`q.op` / `df` / `sow` は未対応 | OR、AND、引用符、boost、タイトルの部分一致が成功 |
| 保証field | `xckan_original_id`、`xckan_title`、`xckan_site_name`、`xckan_site_url`、`xckan_last_updated` | タイトルの保証fieldを優先条件に使用 |
| タイトルfield | 検索時の索引型の明記はない | `xckan_title:"河川"` は1件、`xckan_title:*河川*` は300件。完全一致と部分一致を区別 |
| 元サイトfield | CKAN以外も収集するためfieldは一様ではない | `title:"河川"` は287件だが、未保証のため必須条件にしない |
| 並び順 | 既定は `score desc` | 元サービスの関連度順を維持。重み8/4はタイトル一致を優先するための相対値 |
| format facet | `res_format` 等の集計を返す | canonical別名や未知形式を誤除外しないようResourceで照合 |
| 地域 | 地理的範囲を保証する共通fieldの記載はない | 独自の `area` / `spatial` filterを推測せず、既存の本文fallbackを維持 |

`C++` のエスケープ済みクエリも成功しましたが、全文解析により `C` に関連する結果が
36,224件返りました。構文をリテラル化することと、索引上の文字列完全一致は別です。

## 検索前後の観測

全て `rows=10`。Dataset件数は検索元の `count` であり、precisionやrecallの数値ではありません。
`tests/fixtures/search_ckan_jp/search_observations.json` は、実応答から件数・クエリ・
上位Datasetのタイトルと出典を抜粋した記録です。完全なAPI応答ではありません。

| 本文 | 変更前 | 変更後 | 確認できた差 |
| --- | ---: | ---: | --- |
| 河川 | 1,109 | 1,114 | タイトル「河川」が上位10件外から先頭へ。タイトル部分一致で5件増えた |
| 河川 神奈川県 | 78,374 | 15 | 上位にあった鹿児島県の河川一覧など、片方の語だけの候補が上位10件から外れた |
| 男女別人口 | 38,768 | 1,058 | 複合語を分割した広い一致から、引用句とタイトル部分一致へ絞れた |
| 避難所 横浜市 | 59,721 | 1 | 他市の避難所一覧を除き、横浜市の統計便覧が残った |

横浜市の正式区域名に都道府県まで必須条件として追加すると0件でした。
そのため、既存行政区域一覧で一意な「横浜市」を検索名に使い、同名の「府中市」は
都道府県と市名の両方を残しました。郡名なしの別名も同じ一覧で一意なら使用します。
市名のみ、都道府県と市名が連続した文字列、underscore区切りで使われる表記の違いを、
推測した地理fieldではなく既知の名前で扱います。

## Resource単位の改善

横浜市の統計便覧には83 Resourceがあり、元の順序では人口統計が先頭でした。
実メタデータにある「地域防災拠点（指定避難所）及び広域避難場所一覧」のResource IDは
`3348ebc3-e9d9-41a7-b652-0b6c7c2c1d1c` です。
Dataset内で地名を除いた検索語の名称一致、次に説明文一致を優先することで、
その配布物を先頭にします。地名が名称にある二酸化炭素や税収の表を上位にする問題も避けます。

`yokohama_resource_excerpt.json` は、実Datasetの識別情報と、先頭2 Resourceおよび
名称・説明文で「避難所」に言及する後続Resourceを抜粋したものです。
テストでは合成の応答外枠で包み、元の順序、改善後の先頭、metadataの保持を確認します。
抽出範囲と合成の外枠を、観測した完全応答として扱いません。

Dataset間では、形式照合後の候補を各Datasetから一つずつ巡回します。
別サイトで同じResource IDが付いていても混同せず、ページをまたぐ重複を除きます。
出典には実際に送った `q` / `rows` / `start` を保持します。

## 残る制約

- 本文のANDは全ての検索語に対応する候補を要求します。「避難場所」等への類義語展開はせず、広いOR検索より候補を取りこぼす可能性があります。
- 地名が説明文にあるだけの他地域データが残ります。「河川 神奈川県」では上水道施設、東京都の防災計画、九州の大雨記録も返りました。countの減少だけで地理的精度の向上を断定しません。
- 検索元はDatasetを検索します。Resource名称・説明文の照合は取得後であり、Resourceの名称に検索語がなくてもDatasetが一致すれば候補として残ります。
- 全国版に検索地名が索引されていなければ取得しません。全国・地方への包含検索は、サービスが共通の範囲metadataを保証していないため追加していません。
- 全文の語解析、句読点、収集時期、索引の更新に結果は依存します。重みはすべてのタイトル一致の順位を保証しません。
- 巡回はpage内です。有限limitでは10〜100 Dataset/page、`limit=None` は既定pageのみで、全候補を読み込んで順位付けしません。
- 通常CIは実APIを呼びません。観測fixtureと、重複・paging・形式・出典・公開search→resolveの合成テストを用います。

## 再確認方法

例えば次の2つの公式API呼び出しで、本文の複数語の差を確認できます。
外部サービスへの手動検証であり、CIの必須条件ではありません。

```console
curl --get 'https://search.ckan.jp/backend/api/package_search' --data-urlencode 'q=河川 神奈川県' --data 'rows=10'
curl --get 'https://search.ckan.jp/backend/api/package_search' --data-urlencode 'q=(xckan_title:"河川"^8 OR xckan_title:*河川*^4 OR "河川") AND (xckan_title:"神奈川県"^8 OR xckan_title:*神奈川県*^4 OR "神奈川県")' --data 'rows=10'
```

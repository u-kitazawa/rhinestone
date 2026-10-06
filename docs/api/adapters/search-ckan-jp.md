# SearchCkanJpAdapter（横断CKAN検索アダプター）

`SearchCkanJpAdapter` は search.ckan.jp Backend API を使って複数のCKANカタログを検索し、
元の配布物を解決する `Result` を返します。

[Source Adapter 一覧](../source-adapters.md) · source type: `search-ckan-jp`

## 設定と検索

組み込みCatalogの `search-ckan-jp` Provider に検索先が定義されています。検索には
`text` が必須で、`area`、`format`、`limit` を指定できます。

### 本文と地域

本文は空白（全角空白も含む）で区切り、各語をリテラルとして検索します。
全ての語を明示的なANDで結び、同じ語の重複は除きます。
空または空白だけの本文は通信せず空結果を返します。
利用者が入力したSolr演算子・field指定・ワイルドカードは実行しません。

サービスが保証する `xckan_title` で、タイトル完全一致を8、部分一致を4の重みで
優先し、通常の全文検索も残します。重みはSolrへの相対指定であり、公開スコアや
全てのタイトル一致を全文一致より上に置く保証ではありません。全文検索の語の解析や
句読点の扱いは検索元の索引に依存します。例えば `C++` の記号をエスケープしても、
全文検索の解析で `C` に一致することがあります。類義語は追加しません。

`area` は既存の共通処理で正式区域名を本文へ追加します。Adapter内では、同梱の
行政区域一覧で一意な別名がある場合、`神奈川県横浜市` を `横浜市` として検索し、
都道府県名が省かれた候補も取得します。同名の `府中市` 等は都道府県名と
市区町村名の別条件に分け、他県の同名都市を単独条件で検索しません。
これは地理的範囲の照合ではありません。説明文でその地域に言及するだけの候補は
残り得ます。全国データに対象地域名が索引されていなければ検索できません。
市区町村・郡・区の表記揺れも一律には吸収しません。

### 形式、件数、並び順

`format` はBackend APIへ送らず、対象Resourceの宣言済み形式・MIME typeを照合します。
Datasetはサービスの関連度順を維持し、各page内で形式照合後のResourceを
Datasetごとに一つずつ巡回して返します。Dataset内では、地名を除いた検索語が
Resourceの宣言済み名称に多く一致するもの、次に説明文に多く一致するものを優先します。
同順位は元のResource順を保ち、名称・説明文の文字比較は大文字小文字を区別しません。一つのDatasetに多数のResourceがある場合も、
他のDatasetの候補を先に確認できます。Providerをまたぐ順位付けは行いません。

`limit` は形式照合・重複除去後のResource数です。有限limitでは1回に
`min(100, max(10, limit))` Datasetを要求し、不足すればresponseの `count` に従い
`start` で追加pageを取得します。ページ内で巡回し終えてから次のpageへ進むため、
検索全体を対象とするDataset均等配分ではありません。
`limit=None` では検索元の既定page（公式仕様は10 Dataset）だけを取得します。
`limit=0` では通信しません。元サイトが異なる同じResource IDは別候補として扱います。

```python
from rhinestone import FormatPreset, ProviderId, search

results = search(
    providers=[ProviderId.SEARCH_CKAN_JP],
    text="河川",
    area="神奈川県",
    format=[FormatPreset.PYOGRIO],
    limit=10,
)
```

調査根拠と変更前後の実API観測は[検索改善の調査記録](https://github.com/u-kitazawa/rhinestone/blob/develop/docs/research/search-ckan-jp.md)に
記載しています。通信先のメタデータ、収集時期、索引によって検索結果は変わります。

このSourceはDiscovery専用です。検索結果の `target` は元の配布URL、形式、metadataを持つ
`direct` Configに設定されるため、通常どおり `app.resolve(result)` または `result.resolve()`
でResourceへ解決できます。`Config("search-ckan-jp", ...)` を直接解決することはできません。

検索結果には検索元の `metadata`、`raw_metadata`、`provenance` が保持されます。解決先が
`direct` の場合、これらは `Resource.discovery` に保存され、配布物側のmetadataやprovenance
とは分離されます。

## 対応範囲

- search.ckan.jpが返すpackage/resourceの識別情報と公式配布URLを利用します。
- resourceの形式またはMIME typeが明示されている結果だけを返します。
- HTMLの解析、配布URLの推測、検索結果からのprovider secretの取得は行いません。
- 検索結果に含まれる元カタログURLは出典として保持しますが、検索専用Sourceから直接取得は行いません。

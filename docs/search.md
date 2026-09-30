# データを検索する

`app.search()`は構成済みProviderを横断してResultを返します。検索したSourceと、結果を解決するSourceは同一である必要はありません。

## 文字列と検索パラメータ

```python
results = app.search(text="人口", limit=10)
```

`text`、`area`、`bbox`、`time`、`format`、`limit`をキーワードで指定できます。高度な用途では`SearchQuery`を渡すこともできます。

- `text`: `str`または`None`
- `area`: 行政区域の正式名、別名、または全国地方公共団体コード
- `limit`: `bool`を除く0以上の整数
- `bbox`: 数値4要素のtuple
- `time`: `datetime`または`None`を2要素で保持するtuple
- `format`: `Format`または`FormatPreset`を1つ以上保持するtuple（OR条件）

不正な値はProviderへリクエストする前に`ConfigValidationError`になります。`area`と`bbox`は
同時に指定できません。`bbox`の既存の4数値tuple契約は変更されません。

```python
results = app.search(text="河川", area="神奈川県", limit=10)
```

`area`は検索前に組み込みKnowledge AdapterがCRS84のbboxへ解決します。bbox対応Sourceには
そのbboxを渡し、通常のCKAN、PLATEAU、DCAT、search.ckan.jp、Staticのように明示的なtext
fallbackを持つSourceでは正式区域名を`text`へ追加します。それ以外では`area`を
`unsupported` diagnosticとして残すため、地理条件が無言で失われることはありません。

区域スナップショットは47都道府県と1,918件の市区町村・特別区・政令指定都市の区／市を収録します。
`src/rhinestone/adapters/knowledge/japan_administrative_areas.json`に保存し、
2025年1月1日時点の国土交通省「国土数値情報（行政区域データ）」を共同通信社が加工した
都道府県別境界データからbboxを算出しています（出典：国土交通省、加工：共同通信社、
bbox算出：Rhinestone）。原本の形状を直接集計したものではなく、加工過程で小島などが
省略された地域は検索範囲に含まれない場合があります。厳密な行政界全体を必要とする用途には
利用しないでください。所属未定地7件は市区町村として登録していません。
政令指定都市20市の市全体のbboxは区のbboxの和集合です。

市区町村は正式名（例：`神奈川県横浜市`）または5桁コードで指定できます。
短い地名が複数の区域に一致する場合は、正式名またはコードを指定してください。
曖昧一致や外部geocoderは使用しません。
未知の区域はProviderへアクセスせず、全Sourceに
`reason="area_resolution_failed"`を返します。

CKANに`ckanext-spatial`の`spatial_query`が導入されていることを確認できた場合だけ、
次のようにbbox検索を有効化できます。CKANサイトに拡張がない場合、`ext_bbox`が無視
される可能性があるため既定は無効です。

```python
from rhinestone import Provider, configure

app = configure(sources=(
    Provider("spatial-catalog", "ckan", {
        "endpoint": "https://example.org",
        "spatial_search": True,
    }),
))
results = app.search(text="河川", area="神奈川県")
```

有効時は`area`をbboxへ解決し、`package_search`の`ext_bbox=west,south,east,north`
に送ります。明示した`text`も`q`へ渡します。bboxは区域の矩形範囲であり、
行政区域ポリゴンとの厳密な一致ではありません。

`text` は provider 固有の検索構文を増やさない単一の文字列です。Static、DCAT、e-Stat GIS
のローカル照合では、空白区切りの各語が identifier、title、description などの検索対象に
すべて含まれる場合だけ一致します（大文字・小文字は区別しません）。CKAN、search.ckan.jp、
MLIT DPF は文字列を公式 API へそのまま渡すため、AND、完全一致、部分一致の意味は各 API の
仕様に従います。STAC と OGC API Features は現在 `text` を受け取りません。

形式はcanonical vocabularyの`Format`またはRuntime向け集合の`FormatPreset`で検索できます。
複数指定はOR条件です。Providerが形式検索を宣言する場合は条件を渡し、それ以外は明示された
候補形式をRhinestoneが検索後に絞り込みます。post-filter時の`limit`は絞り込み後に適用します。
URI suffixから形式を推測しません。形式不明の結果を含めるには`Format.UNKNOWN`を明示します。

```python
from rhinestone import Format, FormatPreset

vectors = app.search(format=(FormatPreset.PYOGRIO,), limit=10)
files = app.search(format=(Format.GEOJSON, Format.CSV))
unknown = app.search(format=(Format.UNKNOWN,))
```

Presetは検索候補集合であり、Runtimeでのopen成功を保証しません。最終判定は解決後のExecution
Adapterが行います。collection、asset、provider固有の詳細検索は共通引数にしていません。

`search-ckan-jp` では、`limit` はCKANへのpackage取得数（`rows`）に使われるだけでなく、packageをsupported resourceへ展開した後の結果列にも適用されます。そのため、1つのpackageに複数のresourceがある場合、flattened結果全体が`limit`件に達した時点で後続resourceやpackageの結果が省略されます。`limit=None`ならこの展開後の制限はありません。

CKAN と search.ckan.jp は `limit` を Resource 数として満たすまで package 検索を次ページへ
進めます。最初の package ページに実行可能な Resource がない場合でも、応答の `count` が
あれば `start` を使って後続ページを取得します。`limit=None` は provider の既定 page だけを
取得し、全件走査を暗黙には行いません。

`mlit-dpf` は `text`、`bbox`、`limit` に対応します。明示的なtarget ruleが成立する結果は
CKAN、PLATEAU、STAC、OGC等の構成済みSourceへ委譲され、それ以外は明示representationと
`DPF:downloadURLs` が揃う場合だけDirectへfallbackします。`time` は未対応diagnosticになり、
landing pageだけの結果やformat不明の結果は返しません。Directはfallback専用なので、
target ruleの委譲先には指定できません。

```python
from rhinestone.models import SearchQuery

results = app.search(SearchQuery(bbox=(139.5, 35.5, 140.0, 36.0), limit=10))
```

## Resultを選んで解決する

```python
result = results[0]
resource = app.resolve(result)

print(result.title)
print(result.metadata)
print(resource.uri)
```

`Result`は検索中だけ使う一時的な値です。Provider固有の対象指定はResultに保持されますが、endpointやCredentialは複製されません。

Resultは次の情報を持ちます。

- `discovered_by`: 結果を発見したSource ID
- `target`: `app.resolve()`へ渡す解決先の`Config`
- `metadata` / `provenance`: 発見時に得られた知識
- `raw_metadata`: 発見元が返した未加工の provider metadata

横断CKAN検索の結果は、`discovered_by="search-ckan-jp"`、`target.source_id="direct"` のようになります。`target`は`result.to_config()`で取得できます。解決先が発見元と異なる場合、target側の`resource.metadata` / `resource.provenance` / `resource.source.raw_metadata`を保持したまま、発見元の3つの記録は`resource.discovery`へ保持されます。

国交DPFも同じDiscovery境界を使います。`discovered_by` は構成したDPF Source ID、`target` は
委譲先Sourceまたは `direct` です。解決後もDPF由来情報は `resource.discovery` に分離して残り、
Runtimeは `app.open(result, "gdal", runtime=gdal)` や `resource.open("rasterio", runtime=rasterio)` のように明示します。

## 結果の順序

単一Providerでは、iterationと整数indexingはProviderが返した順序をそのまま使います。
複数Providerでは、`catalog`または`sources`へ構成したProvider順にgroupを連結し、
各group内ではProviderが返した順序を保ちます。したがって`results[0]`は最初に構成した
Providerの先頭結果であり、Providerを横断した「最も関連度が高い結果」ではありません。

Rhinestoneは共通scoreやrerankerを持たないため、異なるProviderのrankingを比較しません。
Source IDの辞書順もrankingには使われず、Source IDをrenameしても構成位置が同じなら
iteration順は変わりません。Provider固有のrankingを扱う場合は、
`results.items()`、`results.keys()`、`results["provider-id"]`でgroupごとに参照してください。

## 検索条件

各Sourceは対応する条件だけを受け取ります。例えば`text`に対応するCKANと`bbox`に対応するSTACを構成している場合、両方を指定しても検索全体は失敗せず、各Sourceへ理解できる条件だけが渡されます。

適用されなかった条件は`results.diagnostics`で確認できます。

```python
for diagnostic in results.diagnostics:
    print(
        diagnostic.source_id,
        diagnostic.reason,
        diagnostic.skipped_conditions,
        diagnostic.missing_conditions,
    )
```

指定条件とSourceの対応が一つもないSourceは、空の検索を実行せずスキップします。Sourceに必須条件がある場合、その条件が指定されていないSourceも検索せずスキップします。`diagnostic.reason`は通常`unsupported`または`missing_required`で、後者では`missing_conditions`に不足条件が入ります。地名を解決できなかった場合は`area_resolution_failed`です。

Providerの通信・metadata取得・response解釈に失敗した場合は、失敗したSourceだけを隔離し、他のSourceの検索結果を返します。この場合は`reason="provider_failure"`となり、`failure_type`に`metadata`または`response`が入ります。検索に必要なCredentialが未登録の場合も同様に隔離し、`failure_type="credential"`を返します。これにより、APIキーを設定していない組み込みSourceがあっても、他のSourceの横断検索は継続します。Provider障害の診断には例外メッセージやtracebackを含めません。全Sourceがこの種の障害になった場合も、空の`SearchResults`と診断を返します。一方、検索クエリの検証失敗、Credential factoryの故障、予期しないプログラムエラーはProvider障害として握りつぶしません。

検索結果は`app.resolve(result)`で直接Resourceへ解決できます。`app.search()`が返したResultでは
`result.resolve()`も同じResourceを返し、発見元と解決先が異なる場合も両側のmetadata、raw metadata、
provenanceを保持します。`result.to_config()`は内部パイプラインを調査する高度なAPIです。

## 実行時間と対応表

`results.executions` は実行した Provider ごとの `source_id`、`elapsed_ms`、`result_count` を
構成順で返します。計測値は Adapter 呼び出し時間であり、provider 間の relevance ranking には
使用しません。fixture / fake transport による性能回帰テストや、アプリケーション側の計測に
利用できます。

各 Adapter の条件、絞り込み段階、ページング、既知の境界は
[検索能力の対照表](search-capabilities.md)を参照してください。

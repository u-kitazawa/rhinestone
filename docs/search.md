# データを検索する

`app.search()`は構成済みProviderを横断して、配信単位のResourceを返します。検索したProviderと、Resourceの`reference`が示すProviderは同一である必要はありません。

## 検索するProviderを選ぶ

```python
from rhinestone import FormatPreset, ProviderId, search

results = search(
    text="河川",
    providers=[ProviderId.GEOSPATIAL_JP],
    format=(FormatPreset.PYOGRIO,),
    limit=20,
)
resource = results[0]
```

`providers`は結果の後処理ではなく、検索前の対象選択です。未選択Providerの検索や通信、
そのProviderに関するdiagnostics / executionsは生成しません。対象順はCatalog順を維持し、
重複指定は1回として扱います。指定配列はSearchQuery内で不変のtupleへコピーします。
`providers=None`は全体、`providers=[]`は検索なしです。空配列ならareaの解決も実行しません。
未知または未構成のIDは通信前に`ConfigValidationError`になります。

`app.search()`と`SearchQuery(providers=[...])`でも同じ指定が使えます。
Provider選択はSource固有の検索条件ではないため、Adapterへ投影するQueryには含めません。

## 文字列と検索パラメータ

```python
results = app.search(text="人口", limit=10)
```

`text`、`area`、`bbox`、`time`、`format`、`limit`、`providers`をキーワードで指定できます。高度な用途では`SearchQuery`を渡すこともできます。

- `providers`: `ProviderId` enumまたは独自Provider ID文字列の配列（list / tuple）
- `text`: `str`または`None`
- `area`: 行政区域の正式名、別名、または全国地方公共団体コード
- `limit`: `bool`を除く0以上の整数または`None`（ProviderごとのResource上限）
- `bbox`: 数値4要素のtuple
- `time`: `datetime`または`None`を2要素で保持するtuple
- `format`: `Format`または`FormatPreset`を1つ以上保持するtuple（OR条件）

不正な値はProviderへリクエストする前に`ConfigValidationError`になります。`area`と`bbox`は
同時に指定できません。`bbox`の既存の4数値tuple契約は変更されません。

`limit`はDatasetや検索応答Itemの件数ではなく、展開後のResource件数を数えます。例えば
1つのSTAC Itemにdata assetが3件あれば3 Resource、1つのDCAT distributionにdownload URLが
2件あれば2 Resourceです。Adapterは配信識別子で安定順序を作り、その順で上限まで返します。
format filterも配信単位で適用されるため、同じDatasetの別形式を一緒に採用・除外しません。

```python
results = app.search(text="河川", area="神奈川県", limit=10)
```

`area`は検索前に組み込みKnowledge Adapterが正式区域名とCRS84のbboxへ解決します。
`area`対応Sourceには正式区域名をそのまま渡します。組み込みG空間情報センターはこの経路で
地域条件を独立して扱います。bbox対応Sourceには
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
from rhinestone.catalogs import Catalog
from rhinestone import Provider, configure

app = configure(
    catalog=Catalog(
        (
            Provider(
                "spatial-catalog",
                "ckan",
                {
                    "endpoint": "https://example.org",
                    "spatial_search": True,
                },
            ),
        )
    )
)
results = app.search(text="河川", area="神奈川県")
```

有効時は`area`をbboxへ解決し、`package_search`の`ext_bbox=west,south,east,north`
に送ります。明示した`text`も`q`へ渡します。bboxは区域の矩形範囲であり、
行政区域ポリゴンとの厳密な一致ではありません。

`text` は provider 固有の検索構文を増やさない単一の文字列です。Static、DCAT、e-Stat GIS
のローカル照合では、空白区切りの各語が identifier、title、description などの検索対象に
すべて含まれる場合だけ一致します（大文字・小文字は区別しません）。汎用CKANと
MLIT DPF は文字列を公式 API へそのまま渡すため、AND、完全一致、部分一致の意味は各 API の
仕様に従います。STAC と OGC API Features は現在 `text` を受け取りません。

G空間情報センターの専用Adapterでは、本文の空白区切りの各語をタイトル全体（title_string）・タグで
部分一致検索し、語同士を明示的ANDで結びます。「川」は「河川」にも一致します。地域指定時はAPI側のarea・tags条件で、指定地域から含有する
都道府県・地方・全国へ段階的に検索します。各段階で本文＋地域名のAPI検索も併用し、
返されたarea・タグで地域一致を照合します。地域無指定の通常検索を混ぜません。
地域metadataによる優先順とDatasetを巡回するResource展開は、このProvider内に限定します。
取得範囲とライブ検証の
制限は[G空間情報センター](api/adapters/geospatial-jp.md)を参照してください。

形式はcanonical vocabularyの`Format`またはRuntime向け集合の`FormatPreset`で検索できます。
複数指定はOR条件です。Providerが形式検索を宣言する場合は条件を渡し、それ以外は明示された
候補形式をRhinestoneが検索後に絞り込みます。post-filter時の`limit`は絞り込み後に適用します。
URI suffixから形式を推測しません。形式不明の結果を含めるには`Format.UNKNOWN`を明示します。
ただし、CKAN系のAdapter内照合では、`XLSX`のような非空の未登録形式は
`Format.UNKNOWN`に一致しません。取得する場合は`format`を省略し、`resource.formats`を
確認してください。Coordinatorによる照合との違いは
[検索能力の対照表](search-capabilities.md)に記載しています。

```python
from rhinestone import Format, FormatPreset

vectors = app.search(format=(FormatPreset.PYOGRIO,), limit=10)
files = app.search(format=(Format.GEOJSON, Format.CSV))
unknown = app.search(format=(Format.UNKNOWN,))
```

Presetは検索候補集合であり、Runtimeでのopen成功を保証しません。最終判定は解決後のExecution
Adapterが行います。collection、asset、provider固有の詳細検索は共通引数にしていません。

Coordinatorによる絞り込みは`Resource.formats`だけを照合し、raw metadataやURIから形式を
補完しません。`limit=None`で取得したProviderの既定範囲を絞るため、指定件数に達するまで
追加pageを取得するとは限りません。CKAN系はAdapter内で形式を照合し、件数が足りなければ
次のpackage pageを取得します。検索時に形式を設定しないProviderもあります。
詳細は[検索能力の対照表](search-capabilities.md)の「形式検索の適用段階」を参照してください。

`search-ckan-jp` は本文をエスケープした語の明示的ANDに変換し、検索元が保証する
タイトルfieldの完全一致・部分一致を優先しながら全文検索を残します。既存のarea本文fallbackで
追加された正式市町村名は、行政区域一覧で一意な別名ならその名前を用い、同名都市では
都道府県と市名を両方保持します。地理的範囲の一致を保証するものではありません。

形式照合後のResourceはDataset内で名称・説明文の検索語一致を優先し、page内の
Datasetを一つずつ巡回します。`limit` は重複除去後のResource数です。
有限limitでは10〜100 Dataset/pageを要求し、単純に `rows=limit` とはしません。
検索語の解釈、表記と取得範囲の制約は[横断CKAN検索](api/adapters/search-ckan-jp.md)を参照してください。


CKAN と search.ckan.jp は `limit` を Resource 数として満たすまで package 検索を次ページへ
進めます。最初の package ページに実行可能な Resource がない場合でも、応答の `count` が
あれば `start` を使って後続ページを取得します。`limit=None` は provider の既定 page だけを
取得し、全件走査を暗黙には行いません。

`mlit-dpf` は `text`、`area`、`bbox`、`format`、`limit` に対応します。
地域は行政コードで検索し、本文はDPFのフレーズ検索を優先して通常検索で補います。
解決可能なcatalog / datasetを検索前に絞り、形式照合後の必要件数までページングします。明示的なtarget ruleが成立する結果は
CKAN、PLATEAU、STAC、OGC等の構成済みSourceへ委譲され、それ以外は明示representationと
`DPF:downloadURLs` が揃う場合だけDirectへfallbackします。`time` は未対応diagnosticになり、
landing pageだけの結果は返しません。Directは明示形式を保持し、Nativeの形式は検索時点では不明です。
[DPFの詳細と制約](api/adapters/mlit-dpf.md)を参照してください。Directはfallback専用なので、
target ruleの委譲先には指定できません。

```python
from rhinestone.models import SearchQuery

results = app.search(SearchQuery(bbox=(139.5, 35.5, 140.0, 36.0), limit=10))
```

## Resourceを選んで開く

```python
resource = results[0]
print(resource.title)
print(resource.metadata)
print(resource.uri)
print(resource.reference)

data = app.open(resource, "rasterio", runtime=rasterio)
```

1つのResourceは1つの配信対象を表します。CredentialのsecretやRuntime実体は保持しません。

- `reference`: 取得先Provider ID、dataset ID、distribution/resource ID、非秘密のparameters
- `metadata` / `provenance`: 配信対象の情報と来歴
- `format` / `media_type`: 明示された配信形式。`formats`はその1形式の集合（不明なら空集合）
- `access_plan`: 配信の実行契約。検索時点で取得先への問い合わせが必要な場合は`None`
- `discovery`: 発見元のmetadata、provenance、raw metadataを分離した記録
- `discovered_by`: discoveryがある場合はそのProvider ID、それ以外はreferenceのProvider ID

横断CKAN検索では、`discovered_by="search-ckan-jp"`、`reference.provider_id="direct"`
のようになります。配信側のmetadata/provenanceと検索元の`discovery`は別々に保持します。

国交DPFのnative targetは、取得先ProviderのReferenceと`access_plan=None`を返します。
`app.open(resource, ...)`はReferenceから対象を取得して実行し、DPFのDiscoveryRecordを保持します。
取得先への明示的な問い合わせには`app.load(resource)`を使えます。
解決後のResourceや、検索時点でAccessPlanが確定したResourceは
`resource.open("rasterio", runtime=rasterio)`でも開けます。
未確定Resourceの`resource.open()`は取得先へ問い合わせず、明示的に失敗します。
未知形式の配信はURLから形式を推測せず、取得後もAccessPlanが生成できなければopenに失敗します。

## 結果の順序

Provider の検索は同期 API の内部で最大4件まで並行実行します。
検索全体は対象 Provider の処理完了を待って返ります。完了順にかかわらず、
結果、診断情報、`executions` は Catalog / configuration 順にまとめます。
各 Provider 内の結果順と診断順も維持します。

単一Providerでは、iterationと整数indexingはProviderが返した順序をそのまま使います。
複数Providerでは、`catalog`へ構成したProvider順にgroupを連結し、
各group内ではProviderが返した順序を保ちます。したがって`results[0]`は最初に構成した
Providerの先頭結果であり、Providerを横断した「最も関連度が高い結果」ではありません。

Rhinestoneは共通scoreやrerankerを持たないため、異なるProviderのrankingを比較しません。
Source IDの辞書順もrankingには使われず、Source IDをrenameしても構成位置が同じなら
iteration順は変わりません。Provider固有のrankingを扱う場合は、
`results.items()`、`results.keys()`、`results["provider-id"]`でgroupごとに参照してください。

## 検索条件

各Sourceは対応する条件だけを受け取ります。例えば`text`に対応するCKANと`bbox`に対応するSTACを構成している場合、両方を指定しても検索全体は失敗せず、各Sourceへ理解できる条件だけが渡されます。

STAC検索では、`data` roleのassetをそれぞれ別Resourceへ展開します。対象assetがないItemや不正な配信metadataはスキップします。`SearchResults.diagnostics`の`reason="item_skipped"`、`resource_identifier`、`detail`から対象Itemと理由を確認できます。

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

## 実行時間と対応表

`results.executions` は実行した Provider ごとの `source_id`、`elapsed_ms`、`result_count` を
構成順で返します。計測値は Adapter 呼び出し時間であり、provider 間の relevance ranking には
使用しません。fixture / fake transport による性能回帰テストや、アプリケーション側の計測に
利用できます。

各 Adapter の条件、絞り込み段階、ページング、既知の境界は
[検索能力の対照表](search-capabilities.md)を参照してください。

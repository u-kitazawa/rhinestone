# MlitDpfAdapter（国交DPF検索アダプター）

`MlitDpfAdapter` は国土交通データプラットフォーム（DPF）のGraphQL APIを検索・発見元として
利用するDiscovery専用Sourceです。

[Source Adapter 一覧](../source-adapters.md) · source type: `mlit-dpf`

## 構成

組み込み定義 `BUILTIN`内の`mlit-dpf` Provider はendpointと論理Credential名だけを持ちます。APIキーは
`credentials` から遅延取得され、`Provider`、`Result`、`Resource`、例外には保存されません。
`MLIT_DPF` は組み込みCatalogに含まれますが、APIキーを登録せず横断検索した場合はDPFだけが
`failure_type="credential"` のdiagnosticとして隔離され、他のSourceの検索は継続します。

```python
from rhinestone.catalogs import Catalog
from rhinestone import Provider, configure

dpf = Provider(
    "dpf",
    "mlit-dpf",
    {
        "endpoint": "https://data-platform.mlit.go.jp/api/v1",
        "credential": "mlit-dpf",
        "target_rules": [
            {
                "catalog_id": "official-catalog-id",
                "dataset_id": "official-dataset-id",
                "source_id": "plateau",
                "settings": {
                    "dataset_id": {"metadata": "provider:dataset_id"},
                    "resource_id": {"metadata": "provider:resource_id"},
                },
            }
        ],
        "representations": {
            "fallback-dataset-id": {
                "format": "gpkg",
                "media_type": "application/geopackage+sqlite3",
            }
        },
    },
)

app = configure(
    catalog=Catalog((dpf, Provider("plateau", "plateau", {"endpoint": "https://example.test/ckan"}))),
    credentials={"mlit-dpf": lambda: load_api_key()},
)
```

`target_rules` の各規則は `catalog_id`、任意の `dataset_id`、委譲先の登録済み
`Provider.id`、target Configの各設定値を取得する `record` または `metadata` selectorを
宣言します。委譲先はConfigを解決できるネイティブSourceでなければなりません。`direct` と
Discovery専用の別 `mlit-dpf` Providerは委譲先に指定できず、構成時に
`ConfigValidationError` になります。dataset固有規則がcatalog規則より優先され、同じ
組み合わせの重複は拒否されます。URL、タイトル、catalog名から提供元やIDを推測しません。

ネイティブ委譲に必要な値がない場合だけ、`representations` にdatasetの形式があり、かつ
metadataに安全な `DPF:downloadURLs` がある結果を `direct` Configへ変換します。
`DPF:dataURLs` はランディングページなのでResource URIには使いません。download URLのschemeは
大文字小文字を区別せずHTTPまたはHTTPSとして検証し、埋め込みCredentialや不正なauthorityを
拒否します。

## 検索と実行

`text`、`area`、WGS84の `bbox=(west, south, east, north)`、`format`、`limit` に対応します。
`time` は未対応として検索diagnosticに記録されます。`limit=None` の返却上限は50 Resource、
`limit=0` はCredential取得も通信もしません。公開検索モデル・Coordinator・解決経路は変更しません。

### DPFの検索仕様に合わせた処理

- `area` は共通の地名解決で得た正式区域名から、同じ行政区域snapshotのコードを参照します。
  都道府県は `DPF:prefecture_code`、市区町村は `DPF:municipality_code` の `is` 条件にします。
  市区町村名を単に本文に足したり、そのbbox内の近隣市町村を混ぜたりしません。
  コードの数値・先頭ゼロの扱いは公式クライアントのsearch条件生成に合わせています。
- `target_rules` のcatalog / datasetと、`representations` のdatasetを `attributeFilter` の
  AND / ORで検索前に絞ります。解決ルールの優先順位やDirect fallbackの条件は維持します。
- 空白以外の `text` がある場合は `phraseMatch: true` を先に検索し、返却上限に満たなければ
  `phraseMatch: false` の通常検索で補います。各段階ではDPFの結果順を保ち、
  catalog ID・dataset ID・data IDの組で重複を除きます。
  複数語のANDや日本語の部分一致を独自に保証するものではなく、通常検索の語分割はDPFに委ねます。
- `first` / `size` / `totalNumber` を使い、解決できないレコードを除外した後も次ページを取得します。
  1回の取得は最大50レコードです。形式条件とResource展開を適用してから返却上限を判定します。
  全件を取得してから並び替える方式ではありません。空ページ・同じレコードしか返らないページで
  続行不能なら `ProviderResponseError` として診断します。
- Direct結果には明示されたrepresentationの形式を `Result.formats` に保持します。
  Native委譲結果の形式は検索段階では未確定なので、`format=(Format.UNKNOWN,)` の対象です。
  URLやDPFの自由記述から形式を推測しません。
- provenanceには利用者の条件、`first`、`size`、`phraseMatch`、解決可能な検索範囲を保持します。
  解決先未設定の構成は検索結果を実行可能Resourceへ変換できず、ページを走査し続けません。

行政コードを持たないレコードや、全国版で対象地域のコードを宣言していないレコードは、
地域検索で残ると保証しません。全国・地方のデータを含めたい場合は `area` を指定せず検索します。
G空間の地域タグによる包含関係をDPFに流用していません。

実APIの結果数・応答時間・順位の比較は、利用者のAPIキーを使う環境での検証が必要です。
この変更では公式仕様・公式クライアントと合成応答による回帰テストを根拠としており、
実サービスに対する検索品質向上率を計測したものではありません。
[調査記録](https://github.com/u-kitazawa/rhinestone/blob/develop/docs/research/mlit-dpf-search.md)に確認範囲と手動検証項目を記載しています。

```python
results = app.search(text="道路", bbox=(139.5, 35.5, 140.0, 36.0), limit=10)
result = results[0]
resource = app.resolve(result)
data = resource.open("pyogrio", runtime=pyogrio)
```

DPFは発見元であり、実行Runtimeを選びません。ネイティブ委譲でもDirect fallbackでも、利用者が
`app.open(result, "gdal", runtime=gdal)`、`resource.open("pyogrio", runtime=pyogrio)` などでRuntimeを明示します。指定した
RuntimeがResource形式と非互換なら、別のRuntimeへ暗黙に切り替えず
`ExecutionAdapterUnavailableError` になります。

署名付き `fileDownloadURLs`、半径・属性検索、互換Runtime一覧APIは対象外です。

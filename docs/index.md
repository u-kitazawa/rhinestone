# Rhinestone documentation

Rhinestoneは、日本の公的・地理空間データを**探し、利用可能なResourceへ解決し、既存の専門ライブラリへ渡すためのPythonライブラリ**です。

日本の公共データを使うときは、データそのものを読む前に多くの作業が発生します。

```text
どの提供元にあるか調べる
→ provider固有の検索APIを呼ぶ
→ dataset / resource / assetを選ぶ
→ identifierやqueryを組み立てる
→ 配布形式やarchiveを確認する
→ credentialを付ける
→ 適切なPythonライブラリで開く
```

Rhinestoneは、この「データを使える状態にするまで」の差異をSourceごとの知識として吸収し、利用者には共通の流れを提供します。

```text
search → resolve → open
```

Rhinestone自身が新しいGISエンジンやDataFrameを作るわけではありません。データを特定して利用可能なResourceまで解決した後は、GDAL、Rasterio、pyogrioなどの既存ライブラリへ処理を渡します。

## 2つの入口

検索は便利な入口ですが、必須ではありません。

### 何を使うか探したい

```python
from rhinestone import SearchQuery, configure, sources

app = configure(
    sources=sources.ALL,
)

results = app.search(SearchQuery(text="河川", limit=5))
result = results["geospatial-jp"][0]
resource = app.resolve(result.to_config())

print(resource.uri)
print(resource.format)
print(resource.metadata)
print(resource.provenance)
```

検索では、各Sourceのcatalog/APIからResource候補を見つけます。

### 使いたいデータをすでに知っている

検索を通さず、Configから直接Resourceを解決できます。

```python
from rhinestone import Config

resource = app.resolve(
    Config(
        source_id="...",
        settings={...},
    )
)
```

探索時は検索を使い、再現可能な処理では確定したConfigから直接解決する、といった使い分けもできます。

## Resourceへ解決する

Rhinestoneの中心は`resolve()`です。

検索結果やprovider固有の設定を、実際に利用できる具体的な`Resource`へ変換します。

`Resource`には、URIやformatだけでなく、metadata、provenance、access planなど、データを利用するために解決された情報が保持されます。

```text
provider固有の指定
        ↓
     resolve()
        ↓
     Resource
  ├─ uri
  ├─ format
  ├─ metadata
  ├─ provenance
  └─ access plan
```

このためRhinestoneの価値は検索の有無に依存しません。

- 何を使うか分からない → `search()` + `resolve()`
- datasetやidentifierを知っている → `resolve()`
- 最終URLもreaderも完全に分かっている → Rhinestoneを使わず既存ライブラリを直接使うこともできます

## 既存ライブラリで開く

RhinestoneはGIS I/O・変換・解析を再実装しません。

```python
import rasterio

from rhinestone import configure, sources

app = configure(
    sources=sources.ALL,
    dependencies={
        "rasterio": lambda: rasterio,
    },
)

resource = app.resolve(...)

with resource.open(adapter="rasterio") as dataset:
    ...
```

Resourceの種類に応じて、GDAL、Rasterio、pyogrioなどの既存runtimeを利用できます。

Rhinestoneが担当するのは「何を、どこから、どの条件で、どう開けるか」を解決するところまでです。format conversion、rasterize、spatial join、分析などは専門ライブラリやGISへ委ねます。

## 日本の公共データに寄せる

Rhinestoneは汎用データframeworkを目指すのではなく、日本の公共データで繰り返し現れるprovider固有の差異を扱います。

現在もe-Stat、G空間情報センター/CKAN、PLATEAU、国土地理院、ODPT、STAC、OGC API Features、DCATなど、異なる提供方式を同じ`Resource`解決フローへ接続しています。

重要なのは、それらを同じデータ型へ変換することではありません。

```text
異なるprovider
異なるidentifier
異なるcatalog/API
異なる配布形式
        ↓
   Rhinestone
        ↓
解決済みResource
        ↓
既存の専門ライブラリ
```

日本固有のprovider knowledgeはRhinestone側に集約し、成熟したprotocol clientやGIS runtimeがある場合はそれらを再実装せず活用する方針です。

## Rhinestoneがやらないこと

Rhinestoneは次のものを目指しません。

- 日本全国のdataset metadataを自前で収集する巨大catalog
- 独自のDataFrame / Raster / GISデータモデル
- GIS空間演算や分析engine
- format変換pipeline
- STAC、CKAN、e-Statなど既存protocol clientの無用な再実装

既存のcatalog、provider API、専門ライブラリの間にある「最後の面倒」を解決する薄いlayerであることを重視します。

## Sourceを選ぶ

```python
from rhinestone import configure, sources

app = configure(
    sources=sources.ALL,
)
```

必要なSourceだけに絞ることもできます。

```python
app = configure(
    sources=(sources.GEOSPATIAL_JP, sources.PLATEAU),
)
```

HTTP通信はRhinestoneに組み込まれているため、Sourceの検索やmetadata取得のためのtransportを通常ユーザーが注入する必要はありません。

## 現在の主要概念

- `SourceDefinition`: どのデータ提供元を使うか
- `SearchQuery`: Sourceを横断して候補を探す条件
- `SearchResult`: 検索で見つかった候補
- `Config`: Source内で何を使うかを指定する
- `Resource`: 解決済みの具体的なデータ
- Source Adapter: provider固有の検索・解決方法の知識
- dependency: GDAL、Rasterio、RDFLib等の外部runtime
- credential: API key / token等のsecret

内部アーキテクチャの詳細は[用語と概念](concepts.md)で説明しています。

`direct`はexternal SourceではなくCore機能なので、`sources.ALL`と無関係に常時利用できます。

## 次に読む

- [Getting started](getting-started.md)
- [用語と概念](concepts.md)
- [アプリケーションを構成する](configuration.md)
- [データを検索する](search.md)
- [Resourceを解決して開く](resolve-and-open.md)
- [対応状況](compatibility.md)
- [APIリファレンス](api.md)

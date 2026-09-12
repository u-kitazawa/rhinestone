# 対応状況と既知の非対応

この文書は Rhinestone 0.1.0 の実装済み範囲を示します。表にない提供元、通信仕様、形式は、
対応しているとは限りません。RhinestoneはURLの拡張子や応答内容だけから形式を推測しません。

「Source Adapter」は提供元のAPIやメタデータを読み取る部分、「Execution Adapter」は確定した
ResourceをGDALなどへ渡す部分です。外部ライブラリの準備は[Runtimeの導入ガイド](runtimes.md)を参照してください。

## 実行環境

| 対象 | 対応範囲 | 補足 |
| --- | --- | --- |
| Python | 3.10 以上 | CI は 3.10〜3.13 を対象にする。 |
| HTTP | Python標準ライブラリ | Sourceメタデータ、DCAT文書、ODPT JSONサービスのHTTP通信はRhinestoneに組み込まれています。 |
| GDAL / Rasterio / pyogrio | 利用者が供給する版 | Rhinestone は version を固定・管理しない。各 adapter が呼ぶ API と対象 format の互換性は利用者側で確認する。検証済み範囲は[Runtimeの導入ガイド](runtimes.md)に記載する。 |

この表は、Rhinestoneが対応する提供元、形式、APIの範囲を示します。外部ライブラリのインストール可能性や
ネイティブライブラリの組み合わせを保証するものではありません。ライブラリごとの導入方法、管理方法、
検証済みバージョンは[Runtimeの導入ガイド](runtimes.md)を参照してください。

## Source Adapter（提供元アダプター）

| source type | 対応する提供仕様・版 | 解決できる対象 | 明示的な制限 |
| --- | --- | --- | --- |
| `ckan` | CKAN Action API (`/api/3/action`) | 指定 resource の公式 download URL | HTML catalog、URL 推測、resource 検索以外の Action API は非対応。 |
| `dcat` | DCAT RDF: JSON-LD、Turtle、RDF/XML | `dcat:downloadURL` を持つ Distribution | 他の RDF serialization、`accessURL` だけの Distribution は非対応。 |
| `direct` | provider 非依存 | 利用者が明示する URI / format | format、media type、実行方法の推測はしない。 |
| `gsi-fundamental` | 基盤地図情報の取得済み basic vector | ローカル GML、ZIP 内の明示 entry point | DEM、ログイン、ダウンロード自動化、ZIP 以外の archive は非対応。 |
| `static` | Catalog または利用者が管理する静的定義（組み込み GSI は `sources.json` の `gsi`） | HTTPS / XYZ / EPSG:3857 / 256 px の PNG・JPEG tile など、定義済み Resource | 定義外 item、未定義のアクセス方式、仕様の推測は非対応。 |
| `odpt` | ODPT v4 | `station`、`railway`、`train` の JSON service query | 公式 filter 以外、Config 内の secret、他 resource type は非対応。 |
| `ogc-features` | OGC API Features 1.0 | collection または feature の service query | WFS、他 OGC API、built-in data reader は非対応。 |
| `plateau` | G 空間情報センター CKAN Action API | 指定 dataset / resource の配布物 | 市区町村・年度からの配布物推測、ZIP 以外の archive は非対応。 |
| `stac` | STAC API 1.0 | collection item の明示 asset、検索 | 検索はItemごとに `data` roleのassetがちょうど1件必要。解決には対応media typeも必要。asset の URL / format 推測、STAC 以外の catalog は非対応。 |

## Execution Adapter と format

| Execution Adapter | 対応 format / access | 非対応・注意点 |
| --- | --- | --- |
| `gdal` | `shapefile`、`geotiff`、`cog`、`netcdf`、`wms`、`gml`、`citygml`、GSI XYZ tile | ZIP URI の `/vsizip/` 変換はこれだけが行う。上記以外の format は選択しない。 |
| `rasterio` | `cog`、`geotiff` | URI と option をそのまま `rasterio.open()` へ渡す。archive 展開や format 変換はしない。 |
| `pyogrio` | `shapefile`、`geojson`、`gpkg`、`flatgeobuf` | URI と encoding だけを `read_dataframe()` へ渡す。archive URI の組み立てはしない。 |
| `json-service` | `application/json` の ODPT service query | 組み込みHTTP runtimeとODPT用request preparerを使用する。他providerのJSON APIを汎用的に実行しない。 |

STAC は Cloud-Optimized GeoTIFF media type を `cog` として扱う。その他 asset は format が明示できないため、Resolver が失敗する場合がある。DCAT、CKAN、PLATEAU、Direct の配布物も、format が上表の Execution Adapter に一致した場合だけ `open()` できる。

共通の representation 定義は `rhinestone.representations` にあり、format の alias と既知の
media type 対応を Source Adapter 間で共有する。format が明示されている場合は media type
より優先し、URL suffix からの推測は行わない。

## 共通の非対応

- GDAL、Rasterio、pyogrio、PyArrow 等を使った format 変換や GIS 処理
- HTML scraping、redirect の追跡、曖昧な Resource・format・URL の推測
- GeoDataFrame、GeoJSON、Arrow、xarray 等への強制変換
- provider API や外部runtime dependency の version 管理
- 表にない provider、認証方式、protocol、archive 形式

新たな対応は、Source Adapter、Resource / AccessPlan、Execution Adapter の変換、fixture による適合テストを一つの垂直スライスとして追加する。

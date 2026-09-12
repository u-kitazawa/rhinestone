# Rhinestoneの例

簡単なResourceの解決から、実際のサービスを使う検索まで、難易度の順に並べています。すべてのコマンドは
リポジトリのルートで実行してください。利用者向けの詳しい説明は[チュートリアル](../docs/tutorials/index.md)を参照してください。

| 例 | 種類 | 内容 |
| --- | --- | --- |
| [01 URIを指定してResourceを作る](01_direct_resource/README.md) | 固定 | ConfigからResourceを作る |
| [02 CKANのShapefile配布物](02_ckan_shapefile/README.md) | 通信あり | CKANのメタデータとZIP配布物 |
| [04 Resourceの情報を確認する](04_inspect_resource/README.md) | 固定 | メタデータと出典情報 |
| [05 利用者が用意したGDALで開く](05_gdal_dependency/README.md) | 外部ライブラリ | GDALを明示的に使う |
| [06 STACのCOGをRasterioで開く](06_stac_cog/README.md) | 通信あり／外部ライブラリ | STAC assetをRasterioへ渡す |
| [07 検索して取得する](07_search_and_fetch/README.md) | 通信あり／デモ | CKAN検索とResultの解決 |

## 共通の準備

```console
git clone <repository-url> rhinestone
cd rhinestone
uv sync --dev
```

例では、提供元、形式、asset、Resourceの識別子を推測しません。通信を伴う例では環境変数から値を渡し、
利用条件と公開状態を確認したデータを選べるようにしています。

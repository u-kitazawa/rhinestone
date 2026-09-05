# Source Adapter

Source Adapter は provider 固有の Config と公式 API を解釈し、`Source` を作ります。
すべて `rhinestone.adapters` から import します。

[API リファレンス](../api.md) · [Execution Adapter](execution-adapters.md)

初めて Adapter を登録する場合は、先に[アプリケーションを構成する](../configuration.md)
を読んでください。HTTP を使う Adapter には `get_json` callback が必要です。各ページの
`Config.settings` は Adapter が検証する値であり、認証 secret 自体を入れる場所ではありません。

| Adapter | source type | API / 配布元 |
| --- | --- | --- |
| [Direct](adapters/direct.md) | `direct` | 利用者が明示する Resource |
| [CKAN](adapters/ckan.md) | `ckan` | CKAN Action API |
| [DCAT](adapters/dcat.md) | `dcat` | DCAT RDF catalog |
| [e-Stat](adapters/estat.md) | `estat` | e-Stat API 3.0 |
| [GSI Fundamental](adapters/gsi-fundamental.md) | `gsi-fundamental` | 基盤地図情報のローカル GML |
| [GSI Tile](adapters/gsi-tile.md) | `gsi-tile` | 国土地理院 XYZ tile |
| [ODPT](adapters/odpt.md) | `odpt` | ODPT v4 |
| [OGC API Features](adapters/ogc-features.md) | `ogc-features` | OGC API Features 1.0 |
| [PLATEAU](adapters/plateau.md) | `plateau` | G 空間情報センター CKAN |
| [STAC](adapters/stac.md) | `stac` | STAC API 1.0 |

`ProviderAdapter` は独自 Source Adapter の基底クラスです。`source_type` と
`load(config: Config) -> Source` を実装します。検索機能を持つ場合だけ
`search(query)` と `search_conditions` を実装します。

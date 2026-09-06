# Source Adapter

Source Adapter は provider 固有の Config と公式 API を解釈し、`Source` を作ります。
利用者はAdapter classを直接import・登録せず、`ProviderConfig.adapter_type`で選びます。

[API リファレンス](../api.md) · [Execution Adapter](execution-adapters.md)

初めてproviderを構成する場合は、先に[アプリケーションを構成する](../configuration.md)
を読んでください。HTTP を使う provider には `http-json` dependency が必要です。各ページの
`Config.settings` は Adapter が検証する値であり、認証 secret 自体を入れる場所ではありません。

| Adapter | adapter type | API / 配布元 |
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

Source Adapter APIは内部契約です。外部Adapter登録機構はまだ公開しません。同じ
adapter typeを異なるsource idへ複数割り当てられます。

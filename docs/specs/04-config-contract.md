# Config 契約

## 役割

Config は「何のデータを利用したいか」を表す宣言的入力です。Source Adapter が provider 固有の schema と検証を所有し、Core に巨大な provider union schema を置きません。

接続先などの Source 固有の固定値は Catalog の `SourceDefinition.settings` に置き、対象指定は Config に置きます。

```yaml
catalog:
  sources:
    geospatial-jp:
      adapter_type: ckan
      settings:
        endpoint: https://www.geospatial.jp/ckan
config:
  source_id: geospatial-jp
  settings:
    resource_id: abcdef
```

e-Stat の例:

```yaml
catalog:
  sources:
    estat:
      adapter_type: estat
      settings:
        endpoint: https://api.e-stat.go.jp/rest/3.0/app/json
        language: J
config:
  source_id: estat
  settings:
    stats_data_id: "0000000000"
```

## 不変条件

- Config は実行によって暗黙に変更されません（MUST NOT）。
- `source_id` は `configure()` で構成された SourceDefinition を参照します（MUST）。
- Adapter 種別と Source 識別子を同一視しません（MUST NOT）。
- provider と対象を解釈するのに必要な情報を明示します（MUST）。
- HTTP の実装、GDAL option、外部 runtime の instance などを原則として含めません（MUST NOT）。
- 不足した URL、format、identifier を推測しません（MUST NOT）。
- 未知または曖昧な値は明示的な失敗にします（MUST）。
- credential が必要な Source は、Config に secret ではなく論理 credential 名だけを記述します（MUST）。

## Catalog と Config の境界

`sources.json` は組み込み Source の接続先・サービス仕様を保持します。利用者が独自の接続先を使う場合は、既存 Adapter に対する `SourceDefinition` を明示して `configure(sources=...)` に渡します。

`sources.json` の各Sourceエントリに `name` を定義し、`rhinestone.sources` の公開名を決めます。`gsi.settings.items` には `std`、`pale` などの対象名と仕様を定義します。Config は `Config("gsi", {"id": "std"})` のように、その名前だけを指定します。GSI タイルの専用 Adapter や専用 loader はありません。

## 追加 Source の Config

`gsi` は `sources.json` に定義された `std`、`pale` などの item 名を `id` で指定します。独自の静的 Source も `SourceDefinition` の `settings.items` に名前と仕様を明示します。

`plateau` は G 空間情報センター CKAN の `dataset_id` または `resource_id` を指定します。ZIP の CityGML を選ぶ場合は `archive: zip` と archive 内の `entry_point` を指定します。市区町村コード・年からの distribution 推測はしません。

`gsi-fundamental` は取得済みのローカル基本項目ファイルを `path` で指定します。`metadata` に mesh、feature type、schema version、download specification version、CRS、公式 source URL を記載します。初期版は DEM とログイン・ダウンロード自動化を扱いません。

`dcat` は RDF 文書の `uri`、`dataset` URI、必要なら `distribution` URI を指定します。`serialization` は `json-ld`、`turtle`、`xml` のいずれかです。実行候補は `dcat:downloadURL` を持つ Distribution に限ります。

`odpt` は `dataset`（`station`、`railway`、`train`）、logical `credential`、公式仕様にある `filters` を指定します。endpoint、type、filter の許可値は Catalog が管理し、token や任意 URL を Config に記載してはなりません。

## SearchResult からの変換

SearchResult は provider 固有 Config を生成できなければなりません（MUST）。変換後の Config は、直接入力された Config と同じ検証・Source 解釈・解決処理を通ります。検索結果から直接 Resource や Data を作ってはなりません（MUST NOT）。

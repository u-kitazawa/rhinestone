# Schema Knowledge Adapter（形式・スキーマ・互換性）

> 文書ステータス: Knowledge Adapterの仕様候補。実装済み公開APIの契約ではない。

## 1. 目的

Schema Adapterは、Resourceの「何であるか」を複数の粒度で記録し、形式判定やExecution
Adapterの選択を誤らないようにする。ファイル拡張子、MIME type、論理形式、プロファイル、
スキーマ版、実データの構造は同じものではない。

たとえば `.json` はJSONという構文しか示さず、GeoJSON、STAC Item、DCAT JSON-LD、Provider
独自JSONを区別しない。Rhinestoneは、Resourceを開くために必要な証拠が不足している場合、
形式を推測せず候補を未解決として扱う。

## 2. 概念モデル

```text
Representation
  ├─ media type (IANA)
  ├─ format name / profile
  ├─ schema identifier / version
  ├─ encoding / compression / archive
  ├─ geometry or domain model
  └─ evidence
          ↓ compatibility assessment
ExecutionCapability
  ├─ reader name
  ├─ accepted representations
  ├─ required runtime
  └─ limitations
```

MIME typeは登録されたメディアタイプ、formatは人間・Providerが用いる論理形式、profileは
同じ形式の制約や意味付け、schema versionは構造の世代を表す。メディアタイプの構文と登録の
考え方は[IANA Media Types](https://www.iana.org/assignments/media-types/media-types.xhtml)と
[RFC 6838](https://www.rfc-editor.org/rfc/rfc6838)を参照する。

Resourceの最小メタデータは次のように分離する。

```yaml
representation:
  media_type: "application/geo+json"
  format: "GeoJSON"
  profile: "https://example.org/profile/roads"
  schema: "https://example.org/schema/roads"
  schema_version: "1.2"
  encoding: "utf-8"
  compression: null
container:
  archive_format: "zip"
  entry_point: "data/roads.geojson"
```

未確認値は空文字や推測値で埋めず、`unknown`または未提供として区別する。

## 3. 互換性の定義

「形式が同じ」と「Runtimeで開ける」は異なる。互換性は少なくとも次の三段階で評価する。

1. **構文互換性**: parserが表現を読めるか。
2. **モデル互換性**: geometry、属性、CRS、時刻、識別子の意味を保てるか。
3. **操作互換性**: 指定されたExecution Adapterが、利用目的に必要な操作を提供できるか。

GDALが開けることは、Providerの論理スキーマが期待通りであることを保証しない。逆に、
同じスキーマでもarchive内部のentry pointや認証付きURLが未指定なら、Resourceは実行可能
ではない。Resolverは、これらの属性とExecution Adapterの宣言を照合する。

暗黙の変換は行わない。GeoJSONをShapefileへ変換したり、CityGMLをGeoPackageへ変換したり
するのはExecutionまたは別の変換ワークフローの責務であり、Schema Adapterの知識出力を
上書きしてはいけない。

## 4. スキーマ版と意味の変更

スキーマ版は文字列として保持し、単純な大小比較で新旧を決めない。`1.10`と`1.9`、日付を
含む版、Provider独自の版を正確に扱うには、スキーマ側の比較規則が必要である。

版が同じでも、Providerが公開するプロファイル、語彙、CRS、コード表が変わることがある。
したがって互換性の判定は、schema URI、profile URI、語彙版、コードリストのsnapshotを
併せて行えるようにする。unknown fieldを捨てず、losslessかどうかを結果に記録する。

JSON Schemaを使う場合も、検証通過はデータの意味的妥当性を保証しない。JSON Schemaの
`required`や型検査、追加プロパティの扱いと、Providerの業務制約は分けて記録する。
[JSON Schema Specification](https://json-schema.org/specification)

## 5. Source／Resolver／Executionとの境界

Source AdapterはProviderの配布メタデータからrepresentationを抽出し、raw metadataを
保持する。Schema Adapterは、メディアタイプと論理形式の対応、profile、schema version、
archive構造、互換性根拠を共有する。Resolverは複数候補を比較し、設定と明示的に一致する
候補だけを選ぶ。

Execution Adapterは、Resourceの選択後に、対応するRuntimeへ渡す。Execution Adapterが
独自に形式を推測したり、別Resourceを探したりしてはいけない。Runtimeが持つドライバの
バージョンも、再現性が必要な場合はProvenanceへ残す。

## 6. 失敗と検証

| 状況 | 期待する扱い |
| --- | --- |
| media typeと内容が矛盾 | provider response / representation error |
| formatだけでprofileが不明 | ambiguous representation |
| schema versionが必要なのに欠落 | incomplete knowledge |
| archiveのentry pointが危険・不明 | validation error |
| Runtimeに対応readerがない | execution unavailable |
| 変換なしでは意味を保てない | unsupported compatibility |

fixtureには、同一拡張子で異なる論理形式、MIME typeだけが違うケース、圧縮アーカイブ、
schema versionの差、GeoJSONのprofile、未知フィールドを含める。検証は「開けたか」だけでなく、
形式・版・profile・元のメタデータがResourceに残るかを確認する。

## 7. 最小垂直スライスと延期

最初は、既存Source Adapterが返す `format` と `media_type` を表現モデルへ昇格し、schema
version、profile、archive entry pointを明示的な属性としてResolverとExecution Adapterへ
渡す範囲がよい。これにより、曖昧な候補を勝手に開く問題を抑えられる。

content sniffing、完全なスキーマ検証、型変換、複数版間の自動migrationは延期する。実装する
場合も、読み取り確認と意味保存を別の機能として評価する。

## 8. 参考資料

- [IANA Media Types](https://www.iana.org/assignments/media-types/media-types.xhtml)
- [RFC 6838: Media Type Specifications and Registration Procedures](https://www.rfc-editor.org/rfc/rfc6838)
- [JSON Schema Specification](https://json-schema.org/specification)
- [OGC API Features](https://ogcapi.ogc.org/features/)

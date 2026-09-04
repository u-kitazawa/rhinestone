# ドメインモデル

Domain 層には、Provider に依存しない Value Object を置く。CKAN、HTTP、pyogrio、GDAL、pandas、その他の統合 Module を Import してはならない（MUST NOT）。

## DataReference

`DataReference` が答えるのは「どのオブジェクトが識別されているか」だけである。Format、Capability、Loader、Timeout、Cache の情報は含まない。

初期の具象 Reference は次のとおり。

```text
CkanResourceReference
  endpoint: absolute HTTP(S) API base URI
  resource_id: non-empty CKAN resource identifier

DirectResourceReference
  uri: absolute HTTP(S) resource URI
```

`CkanResourceReference.endpoint` は、Config の解析時に末尾の Slash を削除して正規化する。これは正規化であり、Endpoint の探索ではない。

Provider 固有の Reference のデータ型は、Domain のインターフェース仕様を実装してもよい（MAY）。その振る舞いは、これらの型ではなく Provider Adapter に属する。

## ResourceMetadata

ソースが提示する、直接アクセス可能な1つの表現。

```text
ResourceMetadata
  identifier: non-empty source identifier
  uri: absolute URI
  format: optional source-provided format label
  media_type: optional source-provided media type
  title: optional title
```

値が存在しないことと、空または不正な値は区別する。Provider が Field の存在を示している場合、Adapter は空の値を拒否することが望ましい（SHOULD）。

## SourceMetadata

Provider が表明する事実。

```text
SourceMetadata
  identifier: non-empty identifier
  title: optional title
  license: optional license expression or label
  authority: source authority URI or identifier
  resources: non-empty ordered tuple of ResourceMetadata
  raw: losslessly retained JSON-compatible provider response
  provenance: MetadataProvenance
```

`resource_show` の場合、`resources` は Resource を正確に1つ含む。複数の Resource を正当に記述する Provider に備えて順序を保持するが、そのような Metadata を対応対象にする前に、後続の Resolver に明示的な選択規則がなければならない（MUST）。

`MetadataProvenance` には次を記録する。

```text
provider: adapter identifier, for example "ckan"
retrieved_from: exact machine-readable endpoint requested
retrieved_at: optional UTC timestamp
```

時刻は観測用 Metadata であり、AccessPlan の等価性に影響してはならない（MUST NOT）。

## Capability と Loader Binding

Capability は安定した意味的識別子である。初期の Capability は次のとおり。

```text
vector.read
```

Loader Binding は、現在の環境で利用可能な実装を提示する。

```text
LoaderBinding
  identifier: stable implementation identifier, for example "pyogrio"
  capability: capability identifier
  priority: integer; lower values are preferred
```

一致する Binding は `(priority, identifier)` で並べて選択する。Registry への挿入順が Plan に影響してはならない（MUST NOT）。

## AccessPlan

初期の具象 Plan は次のとおり。

```text
FileAccessPlan
  uri: absolute resource URI
  format: canonical format identifier
  capability: required capability identifier
  loader: selected LoaderBinding
  source_identifier: metadata identifier
  provenance: plan decision records
```

初期の正規 Format 識別子には、Media に依存しない小文字の名前を使用する。

```text
geopackage
```

Plan の Decision Record は、自明でない各選択を順番に説明する。初期スライスでは、Format の正規化と Loader の選択を含む。テストに使用できる構造化された Code を含まなければならず（MUST）、人間が読めるテキストだけでは不十分である。

例：

```text
format.canonicalized(source="GPKG", result="geopackage")
capability.selected(format="geopackage", result="vector.read")
loader.selected(capability="vector.read", result="pyogrio")
```

## 等価性とシリアライズ

値の等価性には、すべての意味的 Field を含め、取得時刻のように意味を持たないと明記された観測値は除外しなければならない（MUST）。同等の Config、Metadata、Capability Registry で解決処理を繰り返した場合、等しい Plan が生成されなければならない（MUST）。

Domain の値は、JSON 互換の診断用シリアライズを提供することが望ましい（SHOULD）。シリアライズに秘密情報を含めてはならず（MUST NOT）、Plan を理解するのに十分な情報を保持しなければならない（MUST）。保存された Plan は Credential、Resource、インストール済み Loader 実装より長く存続する可能性があるため、Plan のデシリアライズは先送りする。

# 設定仕様

## 入力境界

初期 Parser は、Memory 上の Mapping または JSON Document を受け付ける。YAML 構文も同じ Model で表現できるが、YAML の解析は先送りする。スペルミスによって暗黙に振る舞いが変わらないよう、v0.x では未知の Key をエラーとする。

Config は解析後に不変である。入力 Mapping が後から変更されても Config が変化しないよう、Parser は呼び出し元が所有するネストされた値をコピーしなければならない（MUST）。

## CKAN Config

```yaml
source:
  type: ckan
  endpoint: https://example.jp/api/3
  resource_id: abcdef
```

要件：

- Root は `source` だけを含む。
- `source` は Mapping で、`type`、`endpoint`、`resource_id` だけを含む。
- `type` は `ckan` と完全に一致する。
- `endpoint` は Host を持つ絶対 `http` または `https` URI である。
- `endpoint` は Query または Fragment Component を含んではならない（MUST NOT）。
- 末尾の `/` は削除する。
- `resource_id` は検証後も空でない String であり、それ以外の変更を加えない。

Endpoint は CKAN API の Base で、通常は `/api/3` で終わる。Rhinestone は Protocol で定義された Path `action/resource_show` を追加する。別の Endpoint を試してはならない（MUST NOT）。

## Direct Config

```yaml
source:
  type: direct
  uri: https://example.jp/data.gpkg

data:
  format: geopackage
```

要件：

- Root は `source` と `data` だけを含む。
- `source` は `type` と `uri` だけを含む。
- `type` は `direct` と完全に一致する。
- `uri` は Host を持つ絶対 `http` または `https` URI である。
- `data` は `format` だけを含む。
- `format` は明示された空でない String である。

URI の接尾辞は一切参照しない。Local File Reference は HTTP Resource と Security および Portability の規則が異なるため、別途仕様化する。

## 値の規則

- Boolean、Number、Null、List、Mapping を String に型変換しない。
- Identifier、URI、Format Label の先頭と末尾にある空白は不正とし、暗黙に削除しない。
- Config では URI Credential（`user:password@host`）を不正とする。将来の Credential 機能では、シリアライズされた Domain Value と診断情報の外部に秘密情報を保持しなければならない（MUST）。
- 初期 Resource Type では URI Fragment を不正とする。
- Provider が受け付ける場合は非 ASCII Identifier を受け付ける。Transport Code が Percent Encoding を行う。

## 未対応の Source Type

未知の `source.type` は構造的には有効な JSON だが、インストールされた Application では未対応である。`InvalidConfig` ではなく `UnsupportedSourceType` を送出する。判別値が欠けている、または String でない場合は `InvalidConfig` とする。

## 将来の互換性を保つ発展

Source Type を追加しても、既存 Source の Schema は変更しない。任意 Key を追加する場合は、Default 値と Plan の等価性に影響するかどうかを仕様化する必要がある。未知の Key の扱いを緩和するには、明示的な互換性判断が必要である。各実装が独自に Key を無視し始めてはならない（MUST NOT）。

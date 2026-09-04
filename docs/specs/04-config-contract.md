# Config 契約

## 役割

Config は「何のデータを利用したいか」を表す宣言的入力です。Source Adapter が provider 固有の schema と検証を所有し、Core に巨大な provider union schema を置きません。

```yaml
source:
  type: ckan
  endpoint: https://example.jp
  resource_id: abcdef
```

```yaml
source:
  type: estat
  stats_data_id: "0000000000"
```

## 不変条件

- Config は実行によって暗黙に変更されません（MUST NOT）。
- provider と対象を解釈するのに必要な情報を明示します（MUST）。
- HTTP の実装、GDAL option、外部 runtime の instance などを原則として含めません（MUST NOT）。
- 不足した URL、format、identifier を推測しません（MUST NOT）。
- 未知または曖昧な値は明示的な失敗にします（MUST）。

## SearchResult からの変換

SearchResult は provider 固有 Config を生成できなければなりません（MUST）。変換後の Config は、直接入力された Config と同じ検証・Source 解釈・解決処理を通ります。検索結果から直接 Resource や Data を作ってはなりません（MUST NOT）。

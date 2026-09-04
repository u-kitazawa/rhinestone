# パイプラインとコンポーネント

## データアクセス

```text
Config
  -> [Source Adapter]
  -> Source
  -> [Resolver]
  -> AccessPlan
  -> Resource
  -> [Execution Adapter Selector]
  -> [Execution Adapter]
  -> user-provided dependency
  -> Data
```

### Source Adapter

Config に含まれる provider 固有情報を解釈し、公式の機械可読インターフェースから必要な Metadata を取得して Source を生成します。provider 固有 Reference は Adapter 内部に閉じ込めます。

### Resolver

Source の Resource 候補から、利用する Resource とアクセス方法を決定します。データ本体は原則として読み込みません（MUST NOT）。

### Execution Adapter Selector

Resource と利用可能な依存から適切な Execution Adapter を決定します。利用者による明示指定も受け付けられます。

### Execution Adapter

選択済み Resource を、既存 OSS が理解する URI、open option、layer/subdataset 等へ翻訳します。Resource の選択、汎用データ処理エンジンの実装、runtime dependency の version 管理を行ってはなりません（MUST NOT）。

## 検索

```text
SearchQuery
  -> [Search Coordinator]
  -> searchable [Source Adapter]...
  -> SearchResult[]
  -> Config
  -> normal access pipeline
```

Search Coordinator は検索 Capability を持つ Adapter だけへ問い合わせます。provider 固有 score を同一尺度として直接比較せず、結果は provider ごとのまとまりを保ちます。

## I/O 境界

| コンポーネント | provider metadata I/O | dataset I/O | optional dependency 利用 |
| --- | ---: | ---: | ---: |
| Source Adapter | あり | なし | なし |
| Resolver | なし | なし | なし |
| Search Coordinator / Source Adapter search | あり | なし | なし |
| Execution Adapter Selector | なし | なし | なし |
| Execution Adapter | なし | あり | あり |

Source Adapter の内部は、外部責務境界を守る限り必要になるまで分割を強制しません。通信処理を内部に保持できます。

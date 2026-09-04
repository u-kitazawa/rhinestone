# パイプラインと Port

## 段階

### 1. 解析（Parse）

```text
Mapping -> Config
```

解析では、構造とユーザーが表明した内容だけを確認する。Network I/O、Filesystem の検査、任意 Loader の Import、不足値の推測を行ってはならない（MUST NOT）。

### 2. 参照（Reference）

```text
Config -> DataReference
```

Reference の構築は決定的で、副作用がない。Source Type Registry は、`source.type` の判別値との完全一致で処理を振り分ける。

### 3. 検査（Inspect）

```text
DataReference -> SourceMetadata
```

Adapter Registry は、Reference Type に基づいて正確に1つの Adapter を選択する。Adapter は Metadata I/O を実行してもよい（MAY）が、Resource Data 自体を読み込んではならない（MUST NOT）。

Provider Adapter Port：

```python
class MetadataAdapter:
    def inspect(self, reference):
        """SourceMetadata を返すか、Rhinestone のエラーを送出する。"""
```

### 4. 解決（Resolve）

```text
DataReference + SourceMetadata + Requirements + CapabilityRegistry
  -> AccessPlan
```

解決処理には副作用がない。HTTP Request、Resource の Open、Loader Library の Import を行ってはならない（MUST NOT）。Reference と Metadata の Identifier は、同じ Source Object を指していなければならない（MUST）。

最初のスライスでは `Requirements` は内部用で、Option を含まない。ユーザーが結果またはアクセス方法を選択するユースケースが必要になった後でのみ、公開 Value とする。

### 5. 実行（Execute）

```text
AccessPlan + LoaderRegistry -> Data
```

実行時には、Plan に記録された Binding と完全に一致するものを検索して呼び出す。その Binding が Registry に存在しなくなっている場合は失敗しなければならない（MUST）。暗黙に別の Loader を選択すると、検査した Plan と実際の実行が異なってしまう。

Loader Port：

```python
class Loader:
    capability = "vector.read"
    identifier = "pyogrio"

    def load(self, plan):
        """解決済みの Plan だけを使用してデータを読み込む。"""
```

### 6. 簡易オーケストレーション

```text
plan(config) = parse -> reference -> inspect -> resolve
load(config) = plan -> execute
```

`load(config)` は、呼び出し1回につき Metadata の検査を1回だけ作成しなければならない（MUST）。同じ Registry と Adapter Response のもとで `plan(config)` が生成するものと同じ Plan を実行しなければならない（MUST）。

## Registry

Registry は、v0.x では内部の構成機構である。Application のセットアップ中に構築し、オーケストレーションに渡す。Domain Object は Global を参照しない。

- `ReferenceFactoryRegistry`：`source.type` から Reference Factory への対応。
- `MetadataAdapterRegistry`：Reference Class から Metadata Adapter への対応。
- `CapabilityRegistry`：Capability から利用可能な Loader Binding への対応。
- `LoaderRegistry`：Binding Identifier から Loader Instance への対応。

Registry の構築時に Key が重複した場合は失敗しなければならない（MUST）。必要な Key が存在しない場合は、それを必要とする段階で固有のエラーを送出しなければならない（MUST）。

パッケージは、遅延構築される既定の Application を提供してもよい（MAY）。テストでは、Fake Transport と Fake Loader の境界を持つ独立した Application を構築できなければならない（MUST）。

## 依存関係の方向

```text
public API / application composition
  -> provider adapters  -> transport port
  -> resolution policy  -> domain
  -> loader adapters    -> external OSS
```

Domain は上位のどの層も Import しない。Provider Adapter は Loader を Import しない。Loader Adapter は Provider または Resolution Policy を Import しない。

## I/O の所有権

| 操作 | Metadata I/O | Dataset I/O | 任意 Import |
| --- | ---: | ---: | ---: |
| Config の解析 | なし | なし | なし |
| Reference の構築 | なし | なし | なし |
| Adapter の検査 | あり | なし | なし |
| 解決 | なし | なし | なし |
| 実行 | なし | あり | あり |

pyogrio のような任意 Library は、その Loader Adapter の構築時または使用時にのみ Import しなければならない（MUST）。そのため、その環境または呼び出し元が Binding を明示的に提示した場合に限り、生成された Capability を実行できない環境でも Planning を実行できる。

既定の Application は、Registry の構成時に、Import を伴わない Module の利用可能性チェック（例：`importlib.util.find_spec`）を使用してもよい（MAY）。Module の発見は、その Binding を試行できるという提示にすぎない。実行時に実際の Import が失敗した場合は、引き続き `CapabilityUnavailable` に変換する。テストでは明示的な Binding を使用し、開発者のマシンにインストールされた Module に依存しない。

# Ports 層仕様

## 目的

Port は Application が必要とする外部能力を、配信元、通信 Library、データ処理 OSS から独立して表す。Port は最小の操作と意味的契約だけを定義し、利便機能や具象設定を含めない。

## MetadataAdapter Port

```python
class MetadataAdapter:
    def inspect(self, reference):
        """SourceMetadata を返すか MetadataError を送出する。"""
```

### 契約

- 対応する Reference が指す正確な Object の Metadata を取得する（MUST）。
- Resource Data を読まず、候補検索や Resource 選択を行わない（MUST NOT）。
- 成功時は完全で不変な SourceMetadata を返す（MUST）。
- 配信元の失敗や通信失敗を `MetadataUnavailable`、成功 Response の契約違反を `MetadataInvalid` に分ける（MUST）。
- 元例外は Chaining し、安全で有限な診断 Context を付ける。

Port は通信方式を規定しない。Adapter が Transport Port を使うか、公式 Client を使うかは、Provenance とエラー契約を満たす限り実装判断としてよい。

## Transport Port

```python
class Transport:
    def request(self, request):
        """明示された Request を実行し、Response を返す。"""
```

### 契約

Transport は Request を実行するだけで、Endpoint、Resource、Format、Retry 対象を決めない。Request は Method、完全な URI、有限 Timeout、必要な安全な Header を明示できなければならない（MUST）。Response は Status、Header、Body または Decode 境界を曖昧にしない。

既定 Transport は有限 Timeout と Client を識別する User-Agent を持つ（MUST）。Redirect、Retry、Decode を提供する場合、その Policy を明示し決定的にする。Core は暗黙の Retry を要求しない。Retry は有限であり、配信元が宣言した失敗を別 Endpoint の探索へ変えてはならない（MUST NOT）。

## Loader Port

```python
class Loader:
    identifier = "stable-binding-id"
    capability = "semantic.capability"

    def load(self, plan):
        """選択済み Plan を実行し、外部 OSS の結果を返す。"""
```

### 契約

- `identifier` と `capability` は登録された LoaderBinding と一致する（MUST）。
- 対応する具象 Plan だけを受け付け、Plan の Field だけで実行できる（MUST）。
- Resource、Layer、Format、Protocol、別 Loader を選択しない（MUST NOT）。
- 暗黙の Download、形式変換、CRS 変換、Column 正規化、Data Validation を行わない（MUST NOT）。Capability 契約がそれ自体を要求する場合だけ例外とする。
- 外部 OSS の成功結果を変更せず返す（MUST）。
- 任意依存が利用不能なら `CapabilityUnavailable`、選択済み Resource のアクセス失敗なら `ResourceUnavailable`、完全性検証の失敗なら `IntegrityError` とする。

## Registry 契約

Registry は v0.x の内部構成機構であり、Domain Service Locator ではない。Application の構築時に注入し、Domain Object から参照してはならない（MUST NOT）。

### ReferenceFactoryRegistry

Config の明示的な Source 判別値を1つの Factory に対応付ける。Key の部分一致、Alias、Fallback を暗黙に行わない。

### MetadataAdapterRegistry

Reference の型を1つの Adapter に対応付ける。Subclass を許可する場合も、最も具体的な型など曖昧さのない規則を事前に定義しなければならない（MUST）。初期実装は完全型一致を用いることが望ましい（SHOULD）。

### CapabilityRegistry

Capability ごとの LoaderBinding を保持する。候補を `(priority, identifier)` で並べ、登録順に依存しない選択を可能にする。同じ Identifier が異なる意味を指してはならない（MUST NOT）。

### LoaderRegistry

Binding Identifier を Loader Instance に対応付ける。Executor は Plan の Identifier と完全一致する Entry だけを取得する。

### 共通規則

- 重複 Key または矛盾する登録は構築時に失敗させる（MUST）。後勝ちで上書きしてはならない（MUST NOT）。
- Registry の内容は Application 構築後に不変であることが望ましい（SHOULD）。
- 欠落 Entry は必要になった段階の固有 Error とする（MUST）。
- Registry 構築時の Module 発見は Binding の提示にだけ使ってよい。Planning 中に具象 Module を Import してはならない（MUST NOT）。
- Public Plugin API、Entry Point、登録 Decorator は、実装パターンの反復が確認されるまで契約しない。

## Test Double 契約

Port は小さな Fake で置換可能でなければならない（MUST）。Fake は呼び出し回数と受け取った Value を記録でき、固定結果または指定例外を返せることが望ましい（SHOULD）。適合テストが Port 経由で表現できる場合、Adapter 内部の Monkeypatch に依存してはならない（MUST NOT）。

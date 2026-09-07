# テスト戦略

## Deterministic Tests

通常の CI はネットワークへ依存しない代表 Fixture と golden/contract test を使用します。CKAN、e-Stat、STAC、OGC などの Source Adapter ごとに次を検証します。

- Config から期待する request と Source が得られる。
- 共通 Metadata と raw metadata が保持される。
- Resource 候補から期待する AccessPlan と Resource が決定的に得られる。
- Search Capability が対応条件を処理し、未対応条件を拒否する。
- Federated search がSourceごとにqueryを投影し、未適用条件を診断として返す。
- SearchResult が有効な Config へ変換され、通常フローを通る。
- Execution Adapter が Resource を期待する OSS URI と option へ翻訳する。
- Dependency callback は必要な時点でだけ呼ばれる。
- 推測、silent fallback、暗黙変換、HTML scraping が起きない。
- 異なる失敗原因が異なるエラーとして公開される。

同じ Config、Metadata、利用可能な Capability から同じ AccessPlan が生成されることを、登録順を変えたケースも含めて検証します。

## Live Tests

外部 provider の実 API との適合は scheduled CI で確認し、通常の PR CI から分離します。Live Test は API や schema の変化を検出するために使い、変動する title、件数、timestamp、availability を不変の契約として固定しません。

## 新しい垂直スライス

新しい provider、Resource、access method、Execution Adapter を追加するときは、代表 Fixture、期待モデル、翻訳結果、異常系 matrix、共通適合テストを同じ変更に含めます。

# 契約テスト

テストは、同じブランチの[公開API](../docs/api.md)と[責務境界](../docs/concepts.md)を
実行可能な契約として固定します。過去の設計案を現在のAPIや追加の製品要件として扱いません。
公開契約を変更する場合は、実装・テスト・利用者向け文書を同じ変更で更新します。

## 公開APIと拡張境界

- 通常の経路は`search → Resource → open`、既知の対象は`Reference → app.load()`です。
  検索は配信単位のResourceを返し、metadata、raw metadata、provenance、discoveryを保持します。
- `configure()`は分離されたアプリケーションを作ります。Provider依存ライブラリは`dependencies=`へ、
  遅延factoryは明示的な`RuntimeFactory`で渡します。Runtimeは
  `app.open(resource, name, runtime=...)`または`resource.open(name, runtime=...)`へ実体を渡します。
  Core所有の`json-service` Runtimeは省略できます。Runtimeを暗黙に選びません。
- 公開する名前とシグネチャは[公開APIテスト](test_public_api.py)で確認します。
  詳細なモデルは`rhinestone.models`、原因別エラーは`rhinestone.errors`に置きます。
- Provider/Runtime Adapterの拡張境界は`rhinestone.adapters.contracts`のDefinition/Contextと
  `rhinestone.adapters.ports`です。[Custom Adapterテスト](test_custom_adapters.py)では、
  公開構成経路で登録・依存・認証の境界を検証します。内部Registryの配置を外部契約にしません。
- Knowledge Adapterの`KnowledgeAdapterDefinition`と`KnowledgeAdapterContext`は
  `rhinestone.adapters.knowledge`からimportします。[Knowledgeガイド](../docs/knowledge.md)と
  [Knowledgeテスト](test_knowledge.py)で、`configure(adapters=...)`による登録と共有知識の契約を確認します。

## Providerと実行の検証

同じAdapter型を異なる`Provider.id`で構成でき、Provider Adapterは`Reference`を配信単位の
`Resource`へ読み込みます。Provider Adapterの直接テストでは、小さなfixtureとfake transportで
要求、選択、情報保持、曖昧性、異常応答を確認し、公開search/load経路も別途検証します。
e-Stat統計GISは明示distribution indexを扱い、統計表APIの実装を前提にしません。

Runtime Adapterは選択済み`AccessPlan`を受け取り、Resourceを再選択せず、既存Runtimeの
呼び出しへ翻訳します。形式・ZIP entry point等を推測せず、失敗原因と宛先認可を検証します。
[AccessPlan実行テスト](test_plan_execution.py)では、JSONから復元した計画を、元のResourceや
Providerへの再問い合わせなしで開くことを確認します。[直列化テスト](test_portable.py)では、
Resourceのmetadata/discovery保持、runtime状態の非転送、復元・bindの契約を確認します。

## 決定的なCIと実地確認

通常CIはネットワークに依存しないfixture/fake Runtimeを使います。観測応答の抜粋と合成データは
区別し、fixtureが検証する範囲を超えて外部Providerやnative driverへの適合を保証しません。
live通信や実Runtimeの手動検証は、実行環境・日時・条件・結果を別途記録し、通常CIの成功と区別します。

全品質チェックは[開発ガイド](../CONTRIBUTING.md)に従い`bash scripts/check.sh`で実行します。
対象を絞ったテストが通るだけで、全体のcoverage・lint・型チェック・文書・配布物ビルドを
検証済みとは扱いません。

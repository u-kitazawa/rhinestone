# v0.5 実装状態マトリクス

このページは、設計草案 `spec_v5.md` の主要な判断を現行実装と照合するための
追跡資料です。公開APIの契約は[ドキュメントの位置付け](documentation-status.md)に
示すガイド、APIリファレンス、実装、テストを正本とします。

## 判定規則

| 状態 | 判定基準 |
| --- | --- |
| `Implemented` | 現行実装、回帰テスト、公開ドキュメントの根拠がそろっている |
| `Deferred` | 現時点では実装せず、理由と再評価条件が明示されている |
| `Superseded` | 草案の案を採用せず、現行設計の置換先が明示されている |

## 状態一覧

| ID | `spec_v5.md` の判断 | 状態 | 現行の根拠 | 残作業・再評価条件 |
| --- | --- | --- | --- | --- |
| V05-01 | Resolve First、薄い公開メンタルモデル、`search -> resolve -> open` | `Implemented` | `Rhinestone.search/resolve/open`、`Result.resolve()`、[ホーム](index.md)、[Resourceを解決して開く](resolve-and-open.md)、`tests/test_public_api.py` | 通常利用APIを内部モデルで肥大化させない |
| V05-02 | discovery-driven と Config-driven の2経路 | `Implemented` | `Rhinestone.resolve(Config | Result)`、[データを検索する](search.md)、[Resourceを解決して開く](resolve-and-open.md)、`tests/test_access_vertical_slice.py` | なし |
| V05-03 | Catalog / Provider 定義と同一Adapter型の複数構成 | `Implemented` | `Catalog`、`Provider`、`_ConfiguredSourceAdapter`、[アプリケーションを構成する](configuration.md)、`tests/test_catalogs.py`、`tests/test_public_api.py` | 外部自作Adapterの登録はV05-21で別管理 |
| V05-04 | discovery source と resolution target の分離 | `Implemented` | `Result.discovered_by` と `Result.target`、`Rhinestone.resolve(Result)`、[DiscoveryとResolution](discovery-resolution.md)、`tests/test_public_api.py::test_discovery_result_resolves_through_a_different_target_source` | 両SourceのMetadata / Provenance保持はV05-09bで別管理する |
| V05-05 | federated search、capability projection、diagnostics | `Implemented` | `SearchCoordinator`、`SearchDiagnostic`、[データを検索する](search.md)、`tests/test_search.py` | Provider横断sequenceは非ranking。共通rerankerは導入しない |
| V05-06 | source-scoped search の専用公開API | `Deferred` | 結果は `SearchResults["source-id"]` でProvider別に参照可能だが、検索実行を1 Sourceへ限定する公開引数はない | 特定Providerだけの実行が、Catalogを絞る現行手段では不十分な具体例とAPI形状が確定した時に再評価する |
| V05-07 | Identity / Time / Space の日本横断Knowledge Layer | `Implemented` | `KnowledgeAdapter` の公開境界、snapshot-backed Identity、Time semantics、明示的な Space value、`tests/test_knowledge.py`、`tests/test_open_issue_contracts.py` | Provider projection の追加は同じ canonical value が2 Provider以上で必要になった場合だけ行う |
| V05-08 | Representation knowledge（encoding、archive、配布形式） | `Implemented` | `ResourceCandidate.attributes`、`AccessPlan.options`、GDAL/pyogrio Adapter、[対応状況](compatibility.md)、`tests/test_execution_adapters.py`、`tests/test_resolution.py` | 新しい共通抽象は、同じ知識が2 Provider以上で重複した場合だけ検討する |
| V05-09a | 単一Source内でMetadata / ProvenanceをURLへ縮退させず保持 | `Implemented` | `Metadata`、`Provenance`、`Source`、`Resource`、[DiscoveryとResolution](discovery-resolution.md)、`tests/test_models.py` | 現行のモデル契約を維持する |
| V05-09b | discovery sourceとresolution target双方のMetadata / Provenanceを保持 | `Deferred` | 現行の`Rhinestone.resolve(Result)`は横断Source解決時にdiscovery側の記録でtarget側の記録を上書きする。既存のcross-source回帰テストはtargetが追加記録を持たないため、この損失を検出しない | 両記録を表現するモデルと公開API、競合時の優先規則、cross-provider fixtureを確定してから実装する |
| V05-10 | Source、ResourceCandidate、Resolver、AccessPlan の内部境界 | `Implemented` | `models.py`、`resolution.py`、`pipeline.py`、`tests/test_pipeline.py`、`tests/test_resolution.py` | 通常利用者向けの第一導線には露出しない |
| V05-11 | Existing OSS First とSource/Execution Runtimeの分離 | `Implemented` | Dependency Registry、`RuntimeFactory`、RDFLib Source Runtime、GDAL/Rasterio/pyogrio Execution Runtime、[Runtimeの導入ガイド](runtimes.md)、[外部ライブラリ依存方針](dependency-policy.md)、`tests/test_dependencies.py` | 新規依存は依存方針の採用基準で個別評価する |
| V05-12 | portableなnon-secret resolution境界 | `Implemented` | `Result.target`、`Metadata`、`Provenance`、`AccessPlan`を境界とし、Credential、Runtime、`Resource._opener`を除外する方針を[DiscoveryとResolution](discovery-resolution.md)に記録 | 安定したserialization APIを意味しない。V05-13と分離する |
| V05-13 | versioned `ResourceSpec`、JSON round-trip、汎用Intake export | `Deferred` | Issue #26の評価と[DiscoveryとResolution](discovery-resolution.md)のIntake export評価 | consumer、bind操作、versioned schema、3 Source以上のlossless mappingが確定した場合に再評価する |
| V05-14 | `Resource.open()` と専門Runtimeへのhand-off | `Implemented` | `ExecutionAdapterSelector`、`AccessPipeline._open_resource`、[Resourceを解決して開く](resolve-and-open.md)、`tests/test_execution.py`、`tests/test_execution_adapters.py` | Runtimeのnative objectを返し、共通DataFrame等へ変換しない |
| V05-15 | Credential / Runtime / AccessPlan の分離 | `Implemented` | `CredentialRegistry`、`DependencyRegistry`、`AccessPlan`、[アプリケーションを構成する](configuration.md)、`tests/test_authentication.py`、`tests/test_security.py` | release向けsecurity hardeningは#93、#94、#96、#98、#99で追跡する |
| V05-16 | e-Stat統計表APIと`pyestat`経路 | `Superseded` | #56でRemoveを決定し、#58で実装・公開契約を削除。草案中の`estat-api`例は現行契約ではない | e-Statの新規対応は統計表APIを復活させず、#55の統計GIS discovery/resolutionとして再設計する |
| V05-17 | CKAN、横断CKAN、STAC、PLATEAU、GSI、DCAT、OGC、ODPT、DirectのProvider knowledge | `Implemented` | [対応状況](compatibility.md)、各Source Adapter API、Provider別fixture/contract test | 対応済み範囲を超える仕様をURLや拡張子から推測しない |
| V05-18 | Direct Resourceは補助経路であり中心価値ではない | `Implemented` | `DirectAdapter`、[Resourceを解決して開く](resolve-and-open.md)、`tests/test_direct_adapter.py` | 最終URIとreaderが既知なら専門Runtimeの直接利用を妨げない |
| V05-19 | AI / MCP / GIS integration | `Deferred` | Coreにはintegration framework、巨大native object転送、GIS解析を実装していない | portable consumerと具体的なintegration要件が確定した時にCore外の連携として再評価する |
| V05-20 | Fail Rather Than Guess とdomain error policy | `Implemented` | `errors.py`、Adapter/Resolverの明示検証、`tests/test_errors.py`、`tests/test_provider_edge_cases.py` | 新しい推測規則を追加せず、公式仕様または決定的metadataを根拠にする |
| V05-21 | 外部自作Adapterの登録・公開SDK契約 | `Implemented` | `configure(adapters=...)`、公開 Definition / Context / Port、重複 fail-fast、`tests/test_source_composition.py`、`tests/test_open_issue_contracts.py` | explicit registration を維持し、自動 discovery と process-global registry は導入しない |
| V05-22 | No Scraping、No Central Index、No Transformation Pipeline | `Implemented` | 組み込みHTTP/公式API/静的Catalogをupstreamとし、`open()`後の解析は専門Runtimeへ委譲。[ホーム](index.md)、[DiscoveryとResolution](discovery-resolution.md) | HTML scrapingやGIS解析をCoreへ追加しない |
| V05-23 | 複数SourceでURL passthrough以上のresolution価値を検証 | `Implemented` | [DiscoveryとResolution](discovery-resolution.md)でCKAN、横断CKAN、STAC、PLATEAU、GSIを比較し、fixtureベースのvertical sliceを保持 | 新Sourceも同じ基準でprovider-specific codeを実質的に減らせるか評価する |

## Issue間の責務

- #34 は実データチュートリアル、#36 はRuntime導入・互換性、#37 はAPI安定性・リリース運用として完了済みです。このマトリクスは内容を再定義せず、実装根拠として参照します。
- #49 はKnowledge Layer全体の契約、#50はIdentity、#51はTime、#52はSpaceを担当します。このマトリクスは状態判定だけを担当します。
- #55 はe-Stat統計GISのProvider固有discovery/resolutionを担当し、Knowledge Layerの共通モデルや削除済み統計表APIを再実装しません。
- #93、#94、#96、#98、#99 はrelease前のnetwork/credential security保証を担当します。V05-15の責務分離モデル自体と、各Runtimeでの強制範囲を区別して追跡します。
- V05-09bはこのマトリクスで既知の欠落として記録します。実装時は両Sourceの記録をどう公開するかを専用Issueで決定し、既存の単一Source契約と分離して追跡します。

## #47 の統合判定

この一覧から見た v0.5 統合の判定は次のとおりです。

1. V05-07: #49 の契約に従い、#50（Identity）、#51（Time）、#52（Space）を実装済みとする。
2. V05-16: 統計表 API は Superseded、#55 の e-Stat 統計GIS discovery / resolution は実装済みとする。
3. V05-09b: discovery source と resolution target の記録を一つの既存モデルへ無理に統合せず、両者の公開契約が確定するまで Deferred とする。
4. V05-15: Credential / Runtime / AccessPlan の責務分離と release 向け security hardening を実装・文書化済みとする。
5. V05-06、V05-13、V05-19 は再評価条件が成立するまで Deferred として扱う。V05-21（#85）は explicit registration、stable surface、authoring guide、contract test を含めて Implemented とする。

状態を変更する場合は、同じ変更で根拠となる実装、テスト、公開ドキュメント、関連Issueを更新します。

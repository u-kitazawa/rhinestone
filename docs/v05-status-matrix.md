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

`Deferred` は原則として #47 の blocker ではありません。ただし、既存の明文化済み invariant を満たしていない既知の欠落は例外とし、修正または invariant の明示的変更が完了するまで integration gate に残します。V05-09b がこの例外です。

## 状態一覧

| ID | `spec_v5.md` の判断 | 状態 | 現行の根拠 | 残作業・再評価条件 |
| --- | --- | --- | --- | --- |
| V05-01 | Resolve First、薄い公開メンタルモデル、`search -> resolve -> open` | `Implemented` | `Rhinestone.search/resolve/open`、`Result.resolve()`、[ホーム](index.md)、[Resourceを解決して開く](resolve-and-open.md)、`tests/test_public_api.py` | 通常利用APIを内部モデルで肥大化させない |
| V05-02 | discovery-driven と Config-driven の2経路 | `Implemented` | `Rhinestone.resolve(Config | Result)`、[データを検索する](search.md)、[Resourceを解決して開く](resolve-and-open.md)、`tests/test_access_vertical_slice.py` | なし |
| V05-03 | Catalog / Provider 定義と同一Adapter型の複数構成 | `Implemented` | `Catalog`、`Provider`、`_ConfiguredSourceAdapter`、[アプリケーションを構成する](configuration.md)、`tests/test_catalogs.py`、`tests/test_public_api.py` | 外部自作Adapterの登録はV05-21で別管理 |
| V05-04 | discovery source と resolution target の分離 | `Implemented` | `Result.discovered_by` と `Result.target`、`Rhinestone.resolve(Result)`、[DiscoveryとResolution](discovery-resolution.md)、`tests/test_public_api.py::test_discovery_result_resolves_through_a_different_target_source` | 両Sourceの記録保持はV05-09b / #23で実装済み |
| V05-05 | federated search、capability projection、diagnostics | `Implemented` | `SearchCoordinator`、`SearchDiagnostic`、[データを検索する](search.md)、`tests/test_search.py` | Provider横断sequenceは非ranking。共通rerankerは導入しない |
| V05-06 | source-scoped search の専用公開API | `Deferred` | 結果は `SearchResults["source-id"]` でProvider別に参照可能だが、検索実行を1 Sourceへ限定する公開引数はない | 特定Providerだけの実行が、Catalogを絞る現行手段では不十分な具体例とAPI形状が確定した時に再評価する |
| V05-07 | Identity / Time / Space の日本横断Knowledge Layer | `Implemented` | `KnowledgeAdapter` の公開境界、snapshot-backed Identity、Time semantics、明示的な Space value、`tests/test_knowledge.py`、`tests/test_open_issue_contracts.py` | Provider projection の追加は同じ canonical value が2 Provider以上で必要になった場合だけ行う |
| V05-08 | Representation knowledge（encoding、archive、配布形式） | `Implemented` | CKAN系とe-Stat GISのformat normalization、`ResourceCandidate` / `AccessPlan.options`、GDAL/pyogrio/Rasterio Adapter、[対応状況](compatibility.md)、`tests/test_execution_adapters.py`、`tests/test_resolution.py`、`tests/test_representations.py` | canonical format / media type / archive semantics を `rhinestone.representations` に集約済み |
| V05-09a | 単一Source内でMetadata / ProvenanceをURLへ縮退させず保持 | `Implemented` | `Metadata`、`Provenance`、`Source`、`Resource`、[DiscoveryとResolution](discovery-resolution.md)、`tests/test_models.py` | 現行のモデル契約を維持する |
| V05-09b | discovery sourceとresolution target双方のMetadata / Provenanceを保持 | `Implemented` | `DiscoveryRecord`、`Resource.discovery`、`Result.raw_metadata`、`Rhinestone.resolve(Result)`、cross-source fixture、[DiscoveryとResolution](discovery-resolution.md)、`tests/test_public_api.py` | discovery / target の records を暗黙 mergeせず分離して保持する |
| V05-10 | Source、ResourceCandidate、Resolver、AccessPlan の内部境界 | `Implemented` | `models.py`、`resolution.py`、`pipeline.py`、`tests/test_pipeline.py`、`tests/test_resolution.py` | 通常利用者向けの第一導線には露出しない |
| V05-11 | Existing OSS First とSource/Execution Runtimeの分離 | `Implemented` | Dependency Registry、`RuntimeFactory`、RDFLib Source Runtime、GDAL/Rasterio/pyogrio Execution Runtime、[Runtimeの導入ガイド](runtimes.md)、[外部ライブラリ依存方針](dependency-policy.md)、`tests/test_dependencies.py` | 新規依存は依存方針の採用基準で個別評価する |
| V05-12 | portableなnon-secret resolution境界 | `Implemented` | `Result.target`、`Metadata`、`Provenance`、`AccessPlan`を境界とし、Credential、Runtime、`Resource._opener`を除外する方針を[DiscoveryとResolution](discovery-resolution.md)に記録 | 安定したserialization APIを意味しない。V05-13と分離する |
| V05-13 | versioned `ResourceSpec`、JSON round-trip、汎用Intake export | `Deferred` | Issue #26の評価と[DiscoveryとResolution](discovery-resolution.md)のIntake export評価 | consumer、bind操作、versioned schema、3 Source以上のlossless mappingが確定した場合に再評価する |
| V05-14 | `Resource.open()` と専門Runtimeへのhand-off | `Implemented` | `ExecutionAdapterSelector`、`AccessPipeline._open_resource`、[Resourceを解決して開く](resolve-and-open.md)、`tests/test_execution.py`、`tests/test_execution_adapters.py` | Runtimeのnative objectを返し、共通DataFrame等へ変換しない |
| V05-15 | Credential / Runtime / AccessPlan の分離 | `Implemented` | `CredentialRegistry`、`DependencyRegistry`、`AccessPlan`、[アプリケーションを構成する](configuration.md)、`tests/test_authentication.py`、`tests/test_security.py` | release向けnetwork/credential security hardeningはrelease gateとして別管理し、#47 のarchitecture completionとは分離する |
| V05-16 | e-Stat統計表APIと`pyestat`経路 | `Superseded` | #56でRemoveを決定し、#58で実装・公開契約を削除。草案中の`estat-api`例は現行契約ではない | e-Statの現行対応は #55 の統計GIS discovery/resolution。統計表APIを復活させない |
| V05-17 | CKAN、横断CKAN、STAC、PLATEAU、GSI、DCAT、OGC、ODPT、DirectのProvider knowledge | `Implemented` | [対応状況](compatibility.md)、各Source Adapter API、Provider別fixture/contract test | 対応済み範囲を超える仕様をURLや拡張子から推測しない |
| V05-18 | Direct Resourceは補助経路であり中心価値ではない | `Implemented` | `DirectAdapter`、[Resourceを解決して開く](resolve-and-open.md)、`tests/test_direct_adapter.py` | 最終URIとreaderが既知なら専門Runtimeの直接利用を妨げない |
| V05-19 | AI / MCP / GIS integration | `Deferred` | Coreにはintegration framework、巨大native object転送、GIS解析を実装していない | portable consumerと具体的なintegration要件が確定した時にCore外の連携として再評価する |
| V05-20 | Fail Rather Than Guess とdomain error policy | `Implemented` | `errors.py`、Adapter/Resolverの明示検証、`tests/test_errors.py`、`tests/test_provider_edge_cases.py` | 新しい推測規則を追加せず、公式仕様または決定的metadataを根拠にする |
| V05-21 | 外部自作Adapterの登録・公開SDK契約 | `Implemented` | `configure(adapters=...)`、公開 Definition / Context / TransportPort、Credential・Dependency・Knowledge Port、重複 fail-fast、[Custom Adapterを作る](custom-adapters.md)、`tests/test_source_composition.py`、`tests/test_open_issue_contracts.py` | transport は `SourceAdapterContext.transport` に一本化する |
| V05-22 | No Scraping、No Central Index、No Transformation Pipeline | `Implemented` | 組み込みHTTP/公式API/静的Catalogをupstreamとし、`open()`後の解析は専門Runtimeへ委譲。[ホーム](index.md)、[DiscoveryとResolution](discovery-resolution.md) | HTML scrapingやGIS解析をCoreへ追加しない |
| V05-23 | 複数SourceでURL passthrough以上のresolution価値を検証 | `Implemented` | [DiscoveryとResolution](discovery-resolution.md)でCKAN、横断CKAN、STAC、PLATEAU、GSIを比較し、fixtureベースのvertical sliceを保持 | 新Sourceも同じ基準でprovider-specific codeを実質的に減らせるか評価する |

## Issue間の責務

- #34 は実データチュートリアル、#36 はRuntime導入・互換性、#37 はAPI安定性・リリース運用として完了済みです。このマトリクスは内容を再定義せず、実装根拠として参照します。
- #49 はKnowledge Layer全体の契約、#50はIdentity、#51はTime、#52はSpaceを担当し、いずれも完了済みです。
- #55 はe-Stat統計GISのProvider固有discovery/resolutionを担当し、#56 / #58 の統計表API削除方針と分離して完了済みです。
- #23 は V05-09b の既存 data-retention invariant を担当し、`DiscoveryRecord` と cross-source 回帰テストで完了済みです。
- #85 は外部自作Adapter SDK の transport closure を担当し、`SourceAdapterContext.transport` と conformance evidence で完了済みです。
- #136 は #49 の再評価結果を受け、canonical Representation vocabulary と container/payload semantics を集約して完了済みです。
- release前のnetwork/credential security保証はrelease gateで追跡し、V05-15の責務分離モデルおよび #47 のarchitecture completionとは区別します。

## #47 の統合判定

2026-09-13 時点で、Knowledge Layer、e-Stat GIS、cross-source retention、TransportPort composition、Representation vocabulary の主要ゲートは完了しています。現在の architecture integration 上の未完了ゲートはありません。

1. V05-15 の release向け security hardening は release gate として分離し、#47 の blocker にしない。
2. V05-06、V05-13、V05-19 は再評価条件が成立するまで `Deferred` として扱い、暗黙の実装残件に戻さない。
3. V05-07、V05-16 は完了済みであり、旧 Issue 状態を未完了ゲートとして扱わない。

状態を変更する場合は、同じ変更で根拠となる実装、テスト、公開ドキュメント、関連Issueを更新します。

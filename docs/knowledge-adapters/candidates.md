# Knowledge Adapter 候補一覧

## 文書の目的

Rhinestoneの中心概念は `Catalog -> Provider -> Result -> Resource` である。Providerごとの
接続方法を増やすだけでは、同じ対象を複数のProviderから探すときに、名前・座標・時点・形式・
利用条件の解釈が各Source Adapterへ分散する。Knowledge Adapterは、この解釈をProviderから
切り離し、根拠と不確実性を保持したまま再利用するための知識境界である。

この文書は、現行実装の機能一覧ではなく、コンセプトに照らして投資効果の高い共有知識を
候補化した仕様バックログである。各候補の採用条件は、対応する個別文書に記載する。

## 評価軸

候補は次の5軸で評価した。

| 評価軸 | 問い |
| --- | --- |
| 横断性 | 複数のProvider／Source Adapterで同じ意味が必要か |
| 誤解コスト | 誤った解釈が、別のデータを返す・再現性を壊す・法的リスクを生むか |
| 証拠可能性 | 標準、公式コード表、配布メタデータなどで判断を説明できるか |
| 遅延評価適性 | 構成時ではなく、対象を解決するときに注入・評価できるか |
| Core非侵襲性 | Provider固有処理や外部RuntimeをCoreへ持ち込まずに切り出せるか |

## 優先候補

| 優先 | Knowledge Adapter | 解く問題 | 主な出力 | 初期段階の境界 |
| ---: | --- | --- | --- | --- |
| 1 | [Identity / 地域同一性](identity.md) | 同一自治体・行政区域のコード、改称、合併、別名を同一視する | canonical identity、コード体系、適用期間、照合根拠 | fuzzy match、行政界形状の推定、現在名への自動変換 |
| 2 | [Spatial / 空間参照](spatial.md) | CRS、軸順、bbox、メッシュを同じ意味で扱う | CRS参照、軸順付き範囲、メッシュ識別子、変換可否 | 無根拠な再投影、メッシュからの形状推定、日付変更線の推測 |
| 3 | [Temporal / 時間意味](temporal.md) | 暦年、年度、調査年、観測時刻、有効期間を区別する | typed temporal value、valid time、取得時刻、精度 | timezoneやProvider仕様のない「最新」の推測 |
| 4 | [Schema / 形式・スキーマ](schema.md) | 拡張子・MIME type・論理形式・スキーマ版を混同しない | media type、format profile、schema version、互換性 | bytesの自動変換、未確認のfield mapping、拡張子だけの判定 |
| 5 | [Provenance / 来歴・再現性](provenance.md) | 同じ検索結果を後から説明・再取得できるようにする | source、activity、retrieval、snapshot、checksum、evidence | 内容の完全な監査証跡、第三者の責任判断 |
| 6 | [Rights / ライセンス・利用条件](rights.md) | 出典、ライセンス、用途・期間・再配布条件を候補に結び付ける | rights statement、attribution、制約、確認状態 | 法的可否の自動判定、規約の要約を許諾とみなすこと |

## 推奨する実装順

```text
Provenance foundation -> Identity -> Spatial -> Temporal -> Schema -> Rights
```

意味領域としての優先度はIdentityとSpatialが最も高いが、実装基盤としてはProvenanceの
最小契約を先に追加する。以後の各Adapterが、どのスナップショットと根拠で解決したかを
失わないようにするためである。IdentityとSpatialは、PLATEAU、基盤地図情報、STAC、OGC API Features、統計・CKAN系の
候補を横断して誤解を減らす。Temporalは検索条件とMetadataの双方に現れるため、次に
正規化する価値が高い。SchemaはExecution Adapterとの接続点を明確にし、Provenanceと
Rightsは、研究利用や再配布を含む実運用で「使えた」の根拠を残す。

## 共通契約

すべての候補に共通する最低契約は次のとおりである。

1. 入力の表記と、解決された正規形を分離して保持する。
2. 解決結果に、根拠の出典・スナップショット版・適用期間を付けられる。
3. 一意に定まらない入力、根拠が不足する入力、対象外の入力は推測せず失敗する。
4. Knowledge AdapterはResourceの選択、データ取得、形式変換、外部Runtimeの実行を行わない。
5. Source Adapterは、解決された知識を候補またはResourceのMetadata／Provenanceへ写像する。
6. secretは知識の出力にもスナップショットにも含めない。
7. 同じ入力・同じ知識スナップショット・同じProvider Metadataからは、決定的な結果を返す。

## 完了の判定

個別候補は、説明を書いただけでは完了としない。少なくとも次の受入れ条件を満たした時点で、
実装候補として「確定」とする。

- 標準または一次資料に基づく用語・入力・出力が定義されている。
- 正常系、曖昧系、未知系、境界系の例がある。
- Source Adapter、Resolver、Execution Adapterの責務境界が明記されている。
- 根拠が失われないMetadata／Provenance設計がある。
- 既存Coreへ持ち込まないものが明記されている。
- 決定性、スナップショット、後方互換性の検証方針がある。
- 実装を開始する最小の垂直スライスと、延期する拡張が区別されている。

## 個別文書

- [レビューと実装判断](review.md)
- [Identity / 地域同一性](identity.md)
- [Spatial / 空間参照](spatial.md)
- [Temporal / 時間意味](temporal.md)
- [Schema / 形式・スキーマ](schema.md)
- [Provenance / 来歴・再現性](provenance.md)
- [Rights / ライセンス・利用条件](rights.md)

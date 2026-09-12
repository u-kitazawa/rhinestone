# Provenance Knowledge Adapter（来歴・再現性）

## 1. 目的

Provenance Adapterは、Rhinestoneが「どのProviderの、どのメタデータを、いつ、どの設定で
解決したか」を後から説明できるようにする。検索結果の表示名やURLだけでは、Providerの
更新、検索条件、候補の不採用理由、使用した共有知識の版を再現できない。

W3C PROVは、データの来歴をEntity、Activity、Agentと、それらの関係で表現する。Rhinestone
がいきなり完全な監査グラフを実装する必要はないが、この区別を採用すれば、Providerが公開
したデータ、取得・解決の活動、利用者の設定を混同せずに記録できる。[W3C PROV-O](https://www.w3.org/TR/prov-o/)

## 2. 概念モデル

```text
Agent        Provider / catalog / user application
  │ wasAttributedTo
Activity     search / metadata fetch / resolution / open
  │ used / generated
Entity       catalog response / Result / Resource / data bytes
```

Rhinestoneの既存 `Provenance` は、まず次の最小単位を表す。

```yaml
provenance:
  provider: "example-catalog"
  dataset_identifier: "dataset-123"
  resource_identifier: "distribution-456"
  api_endpoint: "https://example.test/api"
  original_url: "https://example.test/data.zip"
  query_parameters: {q: "河川"}
  retrieved_at: "2026-09-13T01:23:45Z"
  checksum: "sha256:..."
  adapter: "ckan"
  adapter_version: "0.1.0"
  knowledge_snapshots:
    - kind: identity
      version: "2026-04-01"
```

日時は実行ごとに異なるため、決定性の要件は「時刻が固定される」ことではなく、取得時刻を
含めた事実が明示され、同じsnapshotと同じprovider responseから同じ論理結果が得られること
である。

## 3. 再現性の層

再現性を一つのbooleanで示さず、次の層に分ける。

1. **Discovery reproducibility**: 検索条件、Provider、検索結果の順序を再現できる。
2. **Resolution reproducibility**: 同じ候補・Config・knowledge snapshotから同じResourceを
   選べる。
3. **Access reproducibility**: 同じURL・認証・Runtimeで同じデータを取得できる。
4. **Content reproducibility**: checksumやアーカイブ版により同一バイト列を確認できる。
5. **Semantic reproducibility**: schema、CRS、時間・地域の意味が同じであることを説明できる。

URLが同じでも内容が更新されれば、content reproducibilityは成立しない。逆にバイト列が同じ
でも、CRSやスキーマの解釈が欠ければsemantic reproducibilityは不十分である。

## 4. snapshotと証拠

Knowledge Adapterは、入力の解決に使った辞書・標準・コード表・版を「evidence」として返す。
Source AdapterはそれをMetadataまたはProvenanceへ結び付ける。Providerのraw responseを
保持する場合、secret、個人情報、不要な巨大payloadをそのまま保存しない。保持を省略するとき
は、hash、URI、取得時刻、抽出したフィールド、削除理由を残す。

証拠は主張と区別する。

```text
claim: 13104 は新宿区を表す
evidence: e-Stat の snapshot 2026-04-01, record hash=...
method: exact code match
```

「Providerが返した値」と「Rhinestoneが解釈した値」は別フィールドに保存し、推論や既定値を
原データとして表現しない。

## 5. Source／Resolver／Executionとの境界

Source Adapterは、Providerから受け取った識別子、endpoint、query、raw metadataを記録する。
Resolverは、候補集合、選択理由、曖昧性や未選択候補を必要に応じて説明できるようにする。
Execution Adapterは、選択済みResourceを開く活動とRuntime情報を記録するが、Sourceの来歴を
置き換えない。

Provenance AdapterはProviderの正しさやデータ品質を保証しない。また、ユーザーの認証secret、
Authorization header、完全な個人情報を来歴として保存してはいけない。Credentialは「論理名が
使われた」という事実までに留め、secretの値は記録しない。

## 6. 失敗と検証

| 状況 | 期待する扱い |
| --- | --- |
| 必須のProvider identifierがない | incomplete provenance |
| retrieved_atが不正 | provenance validation error |
| checksumのアルゴリズムが不明 | checksumを未確定として扱う |
| raw metadataの出典が不明 | evidence unavailable |
| secretが混入する可能性 | redaction failure として拒否 |
| snapshot版なしの共有知識 | reproducibility warning または拒否 |

テストでは、ResultからResourceへの来歴保持、検索条件の保持、raw metadataの非破壊、候補の
未選択理由、checksum形式、時刻のtimezone、secretの非露出を確認する。`repr`、例外、ログに
secretが出ないことも契約に含める。

## 7. 最小垂直スライスと延期

初期実装は、既存の `Metadata` と `Provenance` を用いて、Provider identifier、元URL、
query、retrieved_at、adapter version、knowledge snapshot versionを失わずに保持する範囲
とする。これだけでも、研究ノートや再調査で「どこから何を選んだか」を説明できる。

PROV-Oの完全なRDFグラフ、実行環境のSBOM、リモートストレージのオブジェクトロック、
改ざん検知署名、データ品質評価は、利用者の要求と脅威モデルを定義してから追加する。記録を
増やすことが目的化し、機密情報や巨大な応答を無制限に保存しない。

## 8. 参考資料

- [W3C PROV-O](https://www.w3.org/TR/prov-o/)
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/)
- [W3C PROV Primer](https://www.w3.org/TR/prov-primer/)
- [W3C PROV-Dictionary](https://www.w3.org/TR/prov-dictionary/)

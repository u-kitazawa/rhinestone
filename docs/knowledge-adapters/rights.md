# Rights Knowledge Adapter（ライセンス・利用条件）

## 1. 目的

Rights Adapterは、Resourceに関係するライセンス、出典表示、利用目的、再配布、アクセス制限、
契約上の注意を構造化し、利用者が解決結果と同時に確認できるようにする。Rhinestoneは法律の
適用可否を裁定するのではなく、Providerが示した権利情報を失わず、未確認・矛盾・継承関係を
明示する。

データの「オープン」という表示だけでは、商用利用、改変、再配布、二次成果物、出典表示、
利用規約への同意条件を決められない。ライセンス名の文字列だけで判定せず、ライセンスURI、
原文、適用対象、取得時点を結び付ける。

## 2. 概念モデル

```text
RightsStatement
  ├─ subject: dataset / distribution / service / metadata
  ├─ license identifier / URI
  ├─ attribution text / URL
  ├─ conditions and restrictions
  ├─ validity / jurisdiction (if stated)
  ├─ source text and snapshot
  └─ confirmation status
```

Resourceに付く権利は一つとは限らない。Datasetのライセンス、Distributionの利用条件、API
の規約、第三者データの継承条件が別々に存在し得る。少なくとも対象を区別し、親Datasetの
権利をDistributionの確定的な許諾へ自動コピーしない。

```yaml
rights:
  - subject: distribution
    license_uri: "https://creativecommons.org/licenses/by/4.0/"
    license_identifier: "CC-BY-4.0"
    attribution: "Example Agency"
    source_url: "https://example.test/terms"
    status: declared
    retrieved_at: "2026-09-13T01:23:45Z"
  - subject: service
    terms_url: "https://example.test/api/terms"
    status: needs-review
```

識別子の語彙には、ライセンス表現を機械処理するためのSPDX等を利用できる。ただし、SPDXの
識別子が対象データの法的結論を自動的に保証するわけではない。[SPDX Specifications](https://spdx.dev/specifications/)

## 3. 情報の優先順位と矛盾

権利情報の出典は、ProviderのResourceメタデータ、Datasetの公式ページ、API規約、ライセンス
本文など複数あり得る。Adapterは出典の優先順位をProviderごとに宣言し、競合した場合に黙って
強い方を採用しない。

- license URIと表示名が一致しない場合は両方を保存し、要確認とする。
- attributionが複数ある場合は削除せず、適用対象と必須性を区別する。
- Data LicenseとTerms of Serviceを同じlicenseフィールドへ入れない。
- APIのレート制限、認証、利用者登録は、著作権ライセンスとは別のAccess Constraintとして保存する。
- 期間・地域・目的の制約は、条件付きstatementとして保持し、無期限の許諾に変換しない。
- ライセンス不明は「制限なし」ではない。

派生データや結合データについては、単純なintersectionで許可範囲を計算しない。各入力の
rights statementと、利用者が行う処理の法的評価が必要である。

## 4. Source／Resolver／Executionとの境界

Source AdapterはProviderのrights fields、利用規約URL、attribution、raw statementを抽出
する。Rights Adapterは、識別子の形式、対象の継承、期限・条件、根拠の有無を標準化する。
Resolverは、利用者が明示した利用目的や要求条件と候補の制約を照合できるが、権利の自動許諾
判断はしない。

Execution Adapterは、必要な出典表示を利用者が実行時に取得できるようResourceへ渡す。ただし、
地図表示や出力ファイルへどの文言を表示するかは利用者のアプリケーション責務である。Rights
Adapterは利用規約を要約して「利用可」と宣言しない。

## 5. 失敗と検証

| 状況 | 期待する扱い |
| --- | --- |
| license URIが不正 | rights validation error |
| 名称とURIが矛盾 | needs-review として保持 |
| attribution必須だが文言なし | incomplete rights |
| 利用規約とライセンスが競合 | rights conflict |
| 期限切れ・適用範囲外 | restricted / not applicable |
| 権利情報がない | unknown。無制限利用とは扱わない |

テストには、標準ライセンスURI、表示名だけのレコード、複数Distribution、DatasetとService
の異なる条件、attributionの継承、期限、規約URL、矛盾したメタデータを含める。出力とログに
元のrights statementとsource URLが残ることを確認する。

## 6. 最小垂直スライスと延期

初期実装は、license URI／表示名、attribution、terms URL、対象、取得時点、確認状態を
Resourceへ保持し、不明を不明のまま返す範囲とする。これにより、GSI、PLATEAU、DCAT、CKAN、
ODPTのように利用条件の表現が異なるProviderを共通の確認画面へ渡せる。

ライセンス互換性の自動判定、自然言語規約の法的解析、派生物の許諾計算、地域ごとの法選択、
利用者契約の自動同意は延期する。これらは法域・契約・利用形態の判断を伴うため、Rhinestone
の「根拠を保持して解決する」という役割を越える。

## 7. 参考資料

- [SPDX Specifications](https://spdx.dev/specifications/)
- [SPDX License List](https://spdx.org/licenses/)
- [W3C DCAT 3](https://www.w3.org/TR/vocab-dcat-3/)
- [Creative Commons About CC Licenses](https://creativecommons.org/share-your-work/cclicenses/)
- [デジタル庁 オープンデータ](https://www.digital.go.jp/resources/open_data)

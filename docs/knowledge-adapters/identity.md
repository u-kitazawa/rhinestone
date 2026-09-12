# Identity Knowledge Adapter（地域同一性）

## 1. 目的

Identity Adapterは、Providerごとに異なる自治体名・地域コード・行政区分を、Rhinestoneが
比較できる同一性へ解決する。これは文字列の正規化ではない。自治体の改称、廃置分合、政令
指定都市の区、都道府県・市区町村・郡などの階層を考慮し、どの時点のどの行政主体を指すかを
明示するための知識である。

e-Statは市区町村コードを地域の表章と相互利用の基準と説明し、合併等による区域変更の都度
改正される一覧と変更情報を提供している。この性質から、コードは不変の主キーではなく、
適用期間を持つ識別子として扱う必要がある。[e-Stat 市区町村名・コード](https://www.e-stat.go.jp/help/municipalities/cities/areacode)

## 2. 概念モデル

```text
provider expression
  ├─ "13104"
  ├─ "新宿区"
  └─ provider-specific IRI
          ↓ evidence-backed resolution
MunicipalityIdentity
  ├─ canonical identifier
  ├─ name / level / parent
  ├─ source code assignments
  ├─ valid time
  └─ resolution evidence
```

`MunicipalityIdentity`は行政主体の同一性、`AreaCode`はあるコード体系における割当、
`AdministrativeUnit`は必要になった場合の区域・階層を表す。これらを一つの文字列へ潰さない。
たとえば「新宿区」という表示名と `13104` は同じ属性ではなく、前者は人間向けのラベル、
後者はあるコード体系での割当である。

最小の解決結果は次のような構造にする。

```yaml
identity:
  canonical_id: "jp-sac:13104"
  name: "新宿区"
  level: municipality
  parent: "jp-sac:13"
  valid_during: "[2015-04-01, 2026-...)"
assignments:
  - scheme: jp-standard-area-code
    value: "13104"
evidence:
  authority: e-stat
  snapshot: "2026-04-01"
  query: "13104"
```

上の値は契約の形を示す例であり、固定の組み込みデータを意味しない。

## 3. 入力と解決規則

入力として許容するのは、Source Adapterが「地域を指定する値」として受け取った明示的な
文字列、コード体系付きコード、または既に構造化されたidentityである。入力の種類を
Provider Adapterが宣言し、Knowledge Adapterは宣言されていない表記を推測しない。

- コード体系と値が明示されている場合は、その組み合わせで照合する。
- 体系なしのコードは、スナップショット内で一意に解釈できる場合だけ受け入れる。
- 名称は完全一致または、スナップショットに明示された別名だけを使う。
- 同じ名称が複数候補に一致する場合は `ambiguous` として失敗する。
- 合併前の名称を現在の名称へ自動変換する場合は、基準日と変更関係が明示されている時だけ行う。
- fuzzy match、読みの推定、都道府県の省略補完は初期契約に含めない。

特に「東京」「中央区」「川越」のような短い名称は、地理的にもっともらしい候補を選んでは
ならない。呼び出し側が親地域、コード体系、基準日を追加して曖昧性を解消する。

## 4. Source Adapterとの境界

Source AdapterはProviderのパラメータ名、APIのコード体系、レスポンスの地域表現を知る。
Knowledge Adapterは、その表現をcanonical identityへ変換する。Source Adapterは変換前の
値と変換結果、使用したスナップショットをSourceのraw metadataへ残し、候補の属性には
canonical identityを参照できる形で保持する。

Knowledge Adapterは次を担当しない。

- ProviderのHTTP APIを検索すること
- 行政界ポリゴンをダウンロード・再投影すること
- 地名から座標やbboxを推定すること
- 欠落したProvider identifierを生成すること
- 最新の行政区域を暗黙に選ぶこと

行政界の形状が必要なら、形状を配布するSource Adapterが別途Resourceとして提示する。
identityの解決結果だけで空間範囲を作ってはいけない。

## 5. スナップショットと履歴

自治体同一性は時間に依存するため、アダプターはデータ版、取得日、基準日、変更履歴の参照
を返せることが望ましい。履歴を扱わない静的実装であっても、スナップショット版を必須にし、
「現時点の名称を返した」のか「調査時点の名称を返した」のかを区別する。

同一コードが異なる期間に異なる主体へ割り当てられる可能性を考慮し、コードだけを永続的な
canonical IDとして扱わない。canonical IDは、少なくともコード体系・値・適用期間、または
それに相当する一次資料上の識別子を含むべきである。

## 6. 失敗と検証

次を別の失敗として表現する。

| 状況 | 期待する扱い |
| --- | --- |
| 空文字・不正な構造 | validation error |
| スナップショットに存在しない | unknown identity |
| 複数主体に一致 | ambiguous identity |
| 指定期間に有効な割当がない | out-of-valid-time |
| Providerへの投影が未定義 | unsupported projection |
| スナップショットを取得できない | knowledge unavailable |

テストには、現行名、別名、同名自治体、合併前後、親子階層、体系付きコード、空値を含める。
さらに、同じスナップショットへ同じ入力を与えた結果が変化しないこと、結果に入力・根拠が
保持されることを検証する。

## 7. 最小垂直スライスと延期

最初の実装は、利用者が注入する自治体スナップショットに対して、完全一致の名称と体系付き
コードを解決し、`MunicipalityIdentity`と証拠を返す範囲に限定する。これだけでも、PLATEAU、
CKAN、統計、基盤地図情報のSource Adapter間で地域条件を再利用できる。

住所ジオコーディング、自然言語検索、行政界の空間重なり判定、過去名称の自動移送は、一次資料
と評価データが揃うまで延期する。便利さより誤ったデータの混入防止を優先する。

## 8. 参考資料

- [e-Stat 市区町村名・コード](https://www.e-stat.go.jp/help/municipalities/cities/areacode)
- [統計LOD 地域に関するデータ](https://data.e-stat.go.jp/lodw/provdata/lodRegion)
- [JIS X 0402（市区町村コード）の案内](https://www.jisc.go.jp/)

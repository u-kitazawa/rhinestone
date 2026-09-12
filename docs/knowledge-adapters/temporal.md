# Temporal Knowledge Adapter（時間意味）

## 1. 目的

Temporal Adapterは、同じ「2020」という文字列が、暦年、年度、調査年、データの有効時点の
どれを表すのかを明示する。時間をdatetimeへ変換するだけでは意味は保存できない。Rhinestone
では、値の型、精度、期間、基準（valid time / publication time / retrieval time）を分離し、
検索条件とResourceの説明に使えるようにする。

ISO 8601は日付・時刻の表記を標準化するが、行政データの「年度」や「調査年」の業務意味まで
決めるものではない。そのため、構文の正規化と、Provider・制度に依存する意味の解釈を別層に
置く。[ISO 8601の概要](https://www.iso.org/iso-8601-date-and-time-format.html)

## 2. 概念モデル

```text
TemporalExpression
  ├─ 2020年
  ├─ 2020年度
  ├─ 令和2年
  ├─ 2020-04-01 / 2020-04-01T00:00:00Z
  └─ Provider-specific survey period
          ↓ explicit semantic resolution
TemporalValue
  ├─ kind
  ├─ start / end or representative value
  ├─ precision
  ├─ timezone / calendar (when applicable)
  ├─ raw expression
  └─ evidence
```

最低限、次の種類を区別する。

| 種類 | 意味 | 典型的な境界 |
| --- | --- | --- |
| `calendar_year` | 1月1日から12月31日までの暦年 | `[YYYY-01-01, (YYYY+1)-01-01)` |
| `fiscal_year` | 制度が定める会計・年度 | Providerまたは制度の定義が必要 |
| `survey_year` | 調査が付与した年次ラベル | 調査要領が意味を決める |
| `valid_time` | 事象・観測・区域が成立する期間 | 閉区間／開区間を明示 |
| `publication_time` | Providerが公開・更新した時点 | Metadataの更新情報 |
| `retrieval_time` | Rhinestoneが取得した時点 | Provenance |
| `as_of_date` | ある日現在という断面 | 日付とtimezoneを明示 |

## 3. 解決規則

アダプターは構文と意味の両方を検証するが、意味のない入力をもっともらしく補完しない。

- `2020年`は、呼び出し側が指定した意味がなければcalendar yearとする。ただし、その既定値
  と根拠を結果へ残す。
- `2020年度`はfiscal year候補であり、4月始まりを暗黙に全Providerへ適用しない。
- `令和2年`のような元号年はcalendar yearへ変換できるが、元号の開始日を跨ぐ日付表現は
  有効性を検証する。
- `2020-04-01`は日付であり、calendar yearやfiscal yearと同一視しない。
- `2020`だけをsurvey yearとして扱うときは、Source Adapterがsurvey semanticsを宣言する。
- 「最新」「現在」「昨年度」は、基準時刻、地域、Providerの更新規則が明示されない限り解決しない。

年だけの値を1月1日00:00へ変換してしまうと、期間の精度を失う。内部では「年の集合」または
`[start, end)`とprecisionを持たせ、必要なExecution Adapterが要求する精度へ明示的に変換する。

## 4. 時区間、境界、timezone

観測期間は、開始・終了の包含規則を持つ。`[start, end)`（開始を含み終了を含まない）と
`[start, end]`を混同しない。終了時刻が欠落している期間は、勝手に日末へ置換しない。

時刻にoffsetがある場合は、元のoffsetと正規化先を保持する。offsetのないローカル時刻へ
timezoneを付与するには、Providerの仕様、地域、夏時間規則が必要である。日本の行政データで
あっても、観測機器や外部APIの時刻をJSTと仮定しない。

暦（Gregorian、Japanese eraなど）と表示言語は、内部の意味と分離する。元号は表示上の表記と
して残しつつ、比較用の値としてGregorian date/yearを返す。閏秒や高精度時刻が必要な分野は、
一般的なdatetimeへ丸めず、unsupported precisionとして扱える設計にする。

## 5. Source Adapterとの境界

Source Adapterは、Providerのパラメータ名（`year`、`fiscalYear`、`datetime`など）と、
その値が何を意味するかを一次資料から宣言する。Temporal Adapterは、値を共通のtyped value
へ変換し、Provider向けに投影する際に意味が失われないかを検査する。

Resolverは候補の有効期間・更新時刻・検索条件を使ってResourceを選ぶが、「新しいファイル
だから対象年に合う」とは判断しない。Execution Adapterは選択済みResourceの時間情報を
使うが、期間の意味を再定義しない。

`retrieved_at`はKnowledge Adapterの結果ではなく、取得活動のProvenanceである。knowledge
の解決時刻とデータ取得時刻を一つにまとめない。

## 6. 失敗と検証

| 状況 | 期待する扱い |
| --- | --- |
| 構文不正・存在しない日付 | validation error |
| 暦・年度の種別が不明 | ambiguous temporal semantics |
| Providerの年度定義が未確認 | unsupported temporal projection |
| timezoneなしの時刻を絶対時刻として要求 | missing timezone evidence |
| 開始・終了の境界が矛盾 | invalid interval |
| 「最新」など基準のない相対表現 | unresolved temporal expression |

テストは、暦年と年度、元号元年、元号境界日前後、ISO日付、無効日、うるう日、開始・終了の
境界、timezone付き／なし、survey yearの明示、相対語の拒否を含む。Provider Adapterの
serializerには、同じ2020でもkindが違えば別パラメータまたは明示的エラーになる契約を置く。

## 7. 最小垂直スライスと延期

初期実装は、明示的な暦年・年度・元号年・ISO日付を typed value として扱い、Source Metadata
と検索条件へ精度・raw value・根拠を保持する範囲とする。これにより、STACやODPTの時刻情報、
PLATEAUや基盤地図情報の年次データを同じ説明枠で扱える。

調査要領を跨いだsurvey yearの自動推定、自然言語の相対日付、複雑な暦、予測期間、タイムゾーン
データベースの同梱は延期する。これらはProvider固有の証拠と更新責任を必要とする。

## 8. 参考資料

- [ISO 8601 Date and Time Format](https://www.iso.org/iso-8601-date-and-time-format.html)
- [OGC API Features Part 1: Core](https://docs.ogc.org/is/17-069r3/17-069r3.html)
- [W3C Time Ontology in OWL](https://www.w3.org/TR/owl-time/)

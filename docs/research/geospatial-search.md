# G空間情報センターの検索改善調査

調査日: 2026-10-06。対象: [Issue #182](https://github.com/u-kitazawa/rhinestone/issues/182)。
コード確認時のdevelop: `3a7361652aa809713c26f190200f396d3e7cc22b`。

これは未完了の調査記録であり、公開APIの仕様や実装済み機能の案内ではありません。
検索処理、Catalog、検索結果の契約は変更していません。

## 公式資料で確認できた事項

根拠はG空間情報センターの[API利用マニュアル（2025年9月版）](https://front.geospatial.jp/how_to_use/manual8/)です。
この環境では本文を直接取得できなかったため、Web検索で取得できた公式本文の範囲を確認しています。
資料に記載された機能と、現在の実APIで検証できた機能を区別します。

| 項目 | 公式資料の記載 | 実APIの確認状況 |
| --- | --- | --- |
| 認証 | 編集と非公開データ取得にはAPIトークンが必要。公開検索のためのトークン要件は記載されていない | 認証なしの成功応答は未取得 |
| `package_search` | `q` と `fq` が掲載されている | 複数語の意味は未検証 |
| タグによる絞り込み | `fq=tags:全国` の利用例がある | 検索結果は未取得 |
| タグの補助API | `tag_list`、`tag_search`、`tag_autocomplete` が掲載されている | 応答形式と一致の意味は未検証 |
| 形式の補助API | `format_autocomplete` が掲載されている | `res_format` による検索可否は未検証 |
| 地域metadata | `area` は全国、地方、都道府県、`都道府県_市区町村` を表す | 実際の値と検索index上のfieldは未検証 |
| 空間metadata | `area` から `spatial` が自動入力される旨の記載がある | `ext_bbox` の対応と包含・交差の意味は未検証 |
| 組織・カテゴリ | `organization_show`、`group_show` などが掲載されている | `fq` で利用できるfieldは未検証 |
| relevance・並び順 | 本調査では十分な記載を取得できていない | デフォルト順と指定可能なsortは未検証 |

公式資料は `fq` で指定できない項目があることも注意しています。
metadataに `area` があることだけを根拠に `fq=area:...` を実装しません。
汎用CKANやSolrの仕様だけで、このProviderの有効fieldや検索挙動を断定しません。

## API取得の観測結果

以下の公開Action APIを認証なしでGETしました。

- `https://www.geospatial.jp/ckan/api/3/action/status_show`
- `https://www.geospatial.jp/ckan/api/3/action/package_search?q=river`

両方ともHTTP 403で、CloudFrontのエラーページが返りました。
本文に `Request blocked.` があり、CKANのJSON応答はありませんでした。
Web取得経路でも検索APIのJSON応答を取得できていません。

これはこの環境からのアクセスの観測であり、Provider全体の障害や認証要件の証明ではありません。
地域制限、アクセス制限、その他の設定のどれが原因かは未特定です。
APIトークンで解消するとは判断できません。

取得可能な環境では、まず次の公開検索がJSONを返すか確認します。

```console
curl --fail-with-body --get --max-time 30 \
  'https://www.geospatial.jp/ckan/api/3/action/package_search' \
  --data-urlencode 'q=河川' --data-urlencode 'rows=5'
```

これは手動調査用のコマンドです。外部APIの成功を通常CIの必須条件にしません。

## 現在の地域条件の受け渡し

組み込み `geospatial-jp` は汎用 `CkanAdapter` を使用しています。
`SearchCoordinator._search_provider()` は区域名をKnowledge Adapterで解決した後、
次のいずれかに置換してからSource Adapterへ渡します。

| Adapterの能力 | 渡される条件 |
| --- | --- |
| `bbox` をサポート | `area=None`、解決済みのbbox |
| `text` をサポートし、地域の本文への連結を許可 | `area=None`、元の本文と正式区域名を連結したtext |
| どちらでもない | `area=None`。地域条件を未対応として診断 |

例えば `text="河川", area="神奈川県"` は、現在のCKAN経路で
`text="河川 神奈川県", area=None` になります。
`ConfiguredSourceAdapter.search()` はこの条件をそのままSource Adapterへ渡します。
専用Adapterの `search_conditions` に `area` を追加するだけでは、元の地域条件は保持されません。

本文末尾の地名を推測して切り離す方法では、利用者が本文に直接書いた地名と独立した地域条件を区別できません。
専用Adapterを直接呼ぶテストだけでは、公開 `search()` の改善を確認できません。

## 実装前に決める境界

Issueの変更範囲を保つ経路として、既存のbboxへの投影とProviderの空間検索を利用できるか調査します。
ただし、`spatial` metadataの存在は空間検索への対応を保証しません。
全国・地方のデータが残るか、未登録の空間metadataがどう扱われるかも検証が必要です。

地域名を独立した条件として専用Adapterへ渡す方式を選ぶ場合、共通処理に
「地域条件を直接扱えるAdapterへ地域名を渡す」分岐が必要になります。
これはIssueの「SearchCoordinatorの共通検索semanticsを変更しない」という制約との調整事項です。
この調査PRでは採用も実装もしていません。

## 残る調査と評価

実応答を取得できる環境で、次を比較・保存します。以下は調査候補であり、有効と確認済みの構文ではありません。

| 対象 | 確認内容 |
| --- | --- |
| 複数語 | 単語、空白区切り、明示的ANDの結果数とDataset ID・順序を比較。日本語の語分割も確認 |
| `fq` | tags、area、organization、groups、res_formatを個別に試し、成功と実際の絞り込みを確認 |
| 地域 | 全国・地方・都道府県・市区町村のmetadataと、対象地域を包含する候補の扱いを確認 |
| 空間 | `ext_bbox` の対応、境界での交差、空間metadata未登録の扱いを確認 |
| タグ | 完全一致と部分一致を区別し、タグ優先が関連Datasetを過剰に除外しないか確認 |
| 並び順 | Providerのデフォルト順と、実際に利用可能なsortを確認 |
| Resource展開 | format・limit適用前後のDataset分布、ページをまたぐ順序と重複を確認 |

代表検索は、河川、河川＋神奈川県、洪水浸水想定区域＋埼玉県、避難所＋市区町村、
学校＋都道府県、PLATEAU＋市区町村とします。
全国・地方Dataset、本文に地名を含むだけのDataset、複数形式のResourceを持つDatasetも含めます。

fixtureには観測した要求条件、取得日、結果順、package・resourceのmetadataを残します。
実応答を加工した場合は加工内容を明示し、合成データを実応答として扱いません。
現時点では応答fixtureも検索品質の改善実績もありません。

実装では、専用Adapterの直接検索に加えて公開 `search()` → `resolve()` の経路を確認します。
Resource単位の結果、format、limit、paging、metadataとprovenanceの保持を検証し、
他のCKAN Providerの挙動とProvider横断の並び順を維持します。

Issue #182は未完了です。API検証と地域条件の受け渡し方針を確定した後、実装・fixture・公開文書を更新します。

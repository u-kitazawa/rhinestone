# 国交DPF検索の最適化調査

調査日: 2026-10-07（日本時間）。対象: `MlitDpfAdapter`。
G空間の方式をコピーするのではなく、DPF自身の検索条件と公式クライアントを根拠にする。
共通公開モデル、Coordinator、Catalogの構造、Credentialと解決境界は変更しない。

## 確認した一次資料

- [検索API仕様](https://data-platform.mlit.go.jp/api_docs/reference/queries/search.html)
- [検索APIサンプル](https://data-platform.mlit.go.jp/api_docs/reference/queries/search_samples.html)
- [GraphiQL入門](https://data-platform.mlit.go.jp/api_docs/tutorials/graphQL/howToUseGraphQL.html)
- [公式MCPクライアント](https://github.com/MLIT-DATA-PLATFORM/mlit-dpf-mcp/blob/main/src/client.py)
  （確認時のfile blob SHA: `67a7c6fe11696c8d53679491e51d7dc9624fe1aa`）


公式ドキュメントの直接GETはこの環境でHTTP 403だった。
Web検索で取得できた公式記述と、GitHubプラグインで全文取得した公式クライアントを区別して使った。
APIキーはこの作業に提供されていないため、認証付き検索の成功応答は取得していない。
合成応答によるテストを実測応答や検索品質の実測値として扱わない。

| 項目 | DPF側の根拠 | 採用する処理 |
| --- | --- | --- |
| キーワード | `term`、`phraseMatch`。公式仕様はtrueを完全一致、初期値をfalseと記載 | 完全一致を優先し、上限未達なら通常検索で補充 |
| 複数語 | 空白の意味・日本語の語分割は今回未検証 | termを保持。独自AND構文や部分一致の保証を追加しない |
| 都道府県・市区町村 | 公式clientの `make_attribute_filter_for_search` にコード属性と `is` がある | 既存行政区域snapshotのコードを明示的属性検索に投影 |
| 地域の包含 | G空間の全国・地方タグと同じ体系は未確認 | 全国・地方を推測で加えない。行政コード未宣言データの制約を公開 |
| カタログ・データセット | 同じ公式helperに `DPF:catalog_id` / `DPF:dataset_id` がある | 明示された解決ルールの範囲へ検索前に絞る |
| 条件結合 | 公式helperのAND、公式search_samplesのAND / OR | 範囲をOR、地域との組み合わせをANDにする |
| 空間 | 公式clientのrectangle生成とbuild_search | 既存bboxの処理を維持。条件のみの検索はtermを空文字で明示 |
| ページ | 公式GraphiQL入門、clientのfirst / size、totalNumber | Resource件数が上限に達するまで取得。1ページ最大50 |
| 形式 | DPFの汎用形式フィルターの根拠は未取得 | Directの明示representationのみ。Nativeの形式はUNKNOWN |
| 順位 | 利用できるrelevance field / 重みの根拠は未取得 | 各段階のProvider順を維持。横断順位は変えない |
| 時間 | DPFは日付属性検索を持つが共通timeと対応する属性を未確定 | 今回は既存の未対応診断を維持 |

## 変更前後の再現テスト

`tests/test_mlit_dpf_adapter.py` の合成GraphQL応答で比較する。

| 入力・応答 | 変更前 | 変更後 |
| --- | --- | --- |
| 河川 + 横浜市 | 行政bboxへ投影 | municipality_code=14100。本文は河川のまま |
| フレーズ一致1件、通常検索に追加2件 | 一致1件のみ | 一致を先頭に保持、追加候補を補う |
| 先頭ページに解決不能レコード、後続に解決可能レコード | 先頭ページで終了 | 後続ページから必要なResourceを返す |
| 指定形式が後続ページにある | 初期50件の後処理に依存 | Adapter内で形式照合し、必要件数まで読み進める |
| 2段階に同じレコードが現れる | 2段階検索なし | catalog・dataset・dataの複合識別で除去 |
| 異なるdatasetに同じdata IDがある | 両方を保持 | 両方を保持 |
| totalが残っているのに空ページ・同じページが返る | ページングなし | 応答エラーとして終了 |

Credentialをprovenanceや例外に含めないこと、Native優先、Direct fallbackの検証、
Resource展開後のlimit、正式区域名の受け渡しを既存・追加テストで確認する。

## 実APIで続けて確認する項目

利用者が登録済みのAPIキーを持つ環境で、検索結果のIDと順序・呼び出し数・経過時間を比較する。
キーをURL、ログ、Notebook出力、Fixtureへ保存しない。

1. 河川・道路・学校・避難所・洪水浸水想定区域でphraseMatch true / falseを比較する。
2. `河川 洪水` の空白区切りがANDかORか、語順と全角空白の影響を調べる。
3. 横浜市、北海道の自治体、先頭ゼロの都道府県コードで数値／文字列の一致を確認する。
4. areaコード検索とbbox検索で、隣接自治体・全国版・属性未宣言データの差を確認する。
5. 解決ルールのcatalog／datasetフィルターが意図したレコードを残すか確認する。
6. 結果を取得できた場合だけ、規約に従って匿名化した小さな応答Fixtureを追加する。

サジェスト・カタログ詳細を全検索に追加すると通信と認証付きAPIの負荷が増えるため、
効果の実測なしでは導入しない。時点や属性の推測、サービス側の順位の模倣も追加しない。

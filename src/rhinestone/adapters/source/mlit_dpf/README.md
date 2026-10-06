# 国交DPF Source Adapter

`mlit-dpf` は、国土交通データプラットフォームのGraphQL APIを利用する検索専用の
Discovery Source Adapterです。
検索時に論理Credentialが未登録の場合は、Search CoordinatorがDPFだけをcredential failureの
diagnosticとして隔離し、他のSourceの検索を継続します。

検索結果は、明示的な `target_rules` に従って既存のSourceへ委譲します。委譲できない場合だけ、
明示された `representations` と `DPF:downloadURLs` を使ってDirectへfallbackします。
規則の委譲先は、構成済みでConfigを解決できるSourceでなければなりません。`direct` および
別の検索専用 `mlit-dpf` Providerを規則の委譲先に指定すると、構成時に拒否されます。

URL、タイトル、catalog名からProvider、識別子、形式を推測しません。ランディングページだけを
示す `DPF:dataURLs` はResource URIとして使用しません。download URLのschemeは大文字小文字を
区別せずHTTPまたはHTTPSとして検証します。


検索はDPFの `attributeFilter` で解決可能なcatalog / datasetと地域コードを絞り、
フレーズ検索を優先して通常検索で補います。`first` / `size` / `totalNumber` による
ページングと重複除去を行い、Resource展開・形式照合後の件数にlimitを適用します。
`area` は都道府県・市区町村コードの属性条件です。コード未宣言の全国版を含む保証はありません。
Directの形式は明示されたrepresentationから保持し、Native委譲の形式は未確定として扱います。

詳細・制約・検証範囲は[APIリファレンス](../../../../../docs/api/adapters/mlit-dpf.md)と
[調査記録](../../../../../docs/research/mlit-dpf-search.md)を参照してください。

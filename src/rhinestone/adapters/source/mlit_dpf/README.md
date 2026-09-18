# 国交DPF Source Adapter

`mlit-dpf` は、国土交通データプラットフォームのGraphQL APIを利用する検索専用の
Discovery Source Adapterです。

検索結果は、明示的な `target_rules` に従って既存のSourceへ委譲します。委譲できない場合だけ、
明示された `representations` と `DPF:downloadURLs` を使ってDirectへfallbackします。
規則の委譲先は、構成済みでConfigを解決できるSourceでなければなりません。`direct` および
別の検索専用 `mlit-dpf` Providerを規則の委譲先に指定すると、構成時に拒否されます。

URL、タイトル、catalog名からProvider、識別子、形式を推測しません。ランディングページだけを
示す `DPF:dataURLs` はResource URIとして使用しません。download URLのschemeは大文字小文字を
区別せずHTTPまたはHTTPSとして検証します。

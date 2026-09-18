# Rhinestone Showcase

Rhinestoneの主要フローを、実行済みのJupyter Notebookとして確認するための入口です。
各Notebookは上から順に実行でき、保存された出力から`Result`、`Resource`、`AccessPlan`を
確認できます。

## Notebook

| Notebook | 内容 | 外部通信 | 追加Runtime |
| --- | --- | --- | --- |
| [01 Search and Resource](01_search_and_resource.ipynb) | 組み込みGSI定義を検索し、`Result`を`Resource`へ解決して来歴とAccessPlanを確認 | 不要 | 不要 |

Notebook冒頭のColabバッジから、そのままGoogle Colabで開けます。ローカルではリポジトリの
開発環境を準備してJupyter互換環境から開いてください。ColabだけはNotebook内のsetup cellが
公開パッケージを導入します。

## 再現性と境界

- `01_search_and_resource.ipynb`は、組み込みの静的GSI定義だけを使います。外部サービスの状態、
  API key、ネットワークに依存せず、通常CIでコードセルを再実行できます。
- 検索結果の並びはProviderの構成順と各Provider内の順序です。Providerをまたぐ関連度ランキング
  ではありません。
- `uri`は外部データの所在地を示しますが、このNotebookはデータ本体を取得せず、`open()`も
  実行しません。
- 保存出力には秘密情報や大きなデータを含めません。Notebookの構文、metadata、再実行結果、
  出力サイズはテストで検証します。
- ライブCKANからベクターデータを開く例、STACからCOGを開く例、Discovery lineageの可視化は
  今後追加します。ライブProviderへの疎通は通常CIの必須条件にしません。

## データと利用条件

最初のNotebookは国土地理院の組み込みメタデータを利用します。解決結果に含まれる
`metadata.raw["usage_url"]`と`usage_notes`を確認し、実データ利用時は提供元の最新条件に従って
ください。Notebookのコード自体はリポジトリと同じMIT Licenseです。

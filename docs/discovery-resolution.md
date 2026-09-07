# Discovery と Resolution の検証

Issue #18 のPhase 0として、現在の5 Sourceを「発見結果から実行可能なResourceへ到達するまで」の観点で比較します。Rhinestoneはcatalog metadataを再収集・再ホストせず、既存のcatalog / provider APIをupstreamとして利用します。

## 比較

| Source | Discoveryで得られる情報 | resolveで補う知識 | 最終的な実行対象 | URL passthroughとの差分 |
| --- | --- | --- | --- | --- |
| e-Stat | `statsDataId`、表題、行政機関 | `getMetaInfo`から統計表を確定し、`getStatsData` queryを組み立てる | e-Stat APIのServiceQuery | ID・言語・API queryを確定する |
| CKAN / GEOSPATIAL_JP | package、resource、format、mimetype | resource metadataとpackage metadataを結合し、配布形態からAccessPlanを選ぶ | concrete file Resource | package/resourceの二段階識別とformat解釈がある |
| STAC | collection、item、asset、bbox、datetime | data assetを一意に選び、COGなどのruntime要件を確定する | COGまたはvector asset | itemから実データassetを選択する |
| PLATEAU | CKAN packageと複数distribution | archive、format、CityGML entry pointを選択する | ZIP内CityGMLまたは配布file | distribution / archive memberを解釈する |
| GSI | catalog定義のtile scheme、CRS、zoom、attribution | tile access planと静的仕様を確定する | XYZ tile Resource | URLだけでなくscheme・CRS・範囲を保持する |

5 Sourceすべてで、少なくとも識別子・配布形態・runtimeへの引き渡し条件を解釈する責務が残ります。したがって、Rhinestoneの責務はデータ処理ではなく、次の境界に限定できます。

```text
discover
  -> provider-specific identity / access を resolve
  -> metadata / provenance を保持
  -> specialist runtimeへ引き渡す
```

## Go / Pivot 判定

現時点ではGoと判定します。

- 複数Sourceで、発見結果から実行対象を確定する処理がURLの受け渡しを超えている。
- discovery sourceとresolution targetを分離する価値がある。`search.ckan.jp`の検索結果は元サイトのmetadataを発見するが、実行にはresource URLを`direct` targetへ変換できる。
- e-Stat、STAC、PLATEAUではprovider固有のID・asset・archive・query解釈が残る。
- GDAL、Rasterio、pyogrio、pyestat、pystacなどの専門runtimeへ処理を委譲しても、ResourceとAccessPlanの決定責務は残る。

一方、Rhinestoneは次を実装しません。

- 全国metadata indexの常設・再ホスト
- HTML scraping
- STAC / CKAN / e-Stat protocolの再実装
- GIS分析、変換、workflow実行

この判断は実装の拡張を無条件に正当化するものではなく、各Sourceでresolutionが利用者側のprovider-specific codeを実際に削減できるかをfixtureとvertical sliceで継続検証します。

## Portable boundary の判断

今回の実装では、runtime-boundな`Resource`全体をそのままJSONやIntakeへ変換する公開APIは追加しません。portableな境界は次のdomain情報です。

- `SearchResult.target`（解決先`Config`）
- `Metadata`
- `Provenance`
- `AccessPlan`のprovider非依存な値

Credential、runtime instance、`Resource._opener`はこの境界に含めません。`SearchResult`はtarget Configへ変換して別Sourceへ解決でき、解決後はアプリケーション側のResourceへ発見時のmetadata / provenanceを引き継ぎます。JSON schemaやIntake exportは、複数Sourceで情報損失と利用価値を確認してから追加します。

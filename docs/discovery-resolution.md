# 発見と解決の検証

Issue #18 のPhase 0として、現在の5 Sourceを「発見結果から実行可能なResourceへ到達するまで」の観点で比較します。Rhinestoneはcatalog metadataを再収集・再ホストせず、既存のcatalog / provider APIをupstreamとして利用します。

## 比較

| Source | Discoveryで得られる情報 | resolveで補う知識 | 最終的な実行対象 | URL passthroughとの差分 |
| --- | --- | --- | --- | --- |
| CKAN / GEOSPATIAL_JP | package、resource、format、mimetype | resource metadataとpackage metadataを結合し、配布形態からAccessPlanを選ぶ | concrete file Resource | package/resourceの二段階識別とformat解釈がある |
| Search CKAN JP | dataset、resource、元catalog URL | 元catalogのResourceへ解決するための識別情報を保持する | concrete file Resource | 横断検索結果から元catalogへ戻る |
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

## 継続判断

現時点ではGoと判定します。

- 複数Sourceで、発見結果から実行対象を確定する処理がURLの受け渡しを超えている。
- discovery sourceとresolution targetを分離する価値がある。`search.ckan.jp`の検索結果は元サイトのmetadataを発見するが、実行にはresource URLを`direct` targetへ変換できる。
- STAC、PLATEAUではprovider固有のID・asset・archive・query解釈が残る。
- GDAL、Rasterio、pyogrio、pystacなどの専門runtimeへ処理を委譲しても、ResourceとAccessPlanの決定責務は残る。

一方、Rhinestoneは次を実装しません。

- 全国metadata indexの常設・再ホスト
- HTMLのスクレイピング
- STAC / CKAN protocolの再実装
- GIS分析、変換、workflow実行

この判断は実装の拡張を無条件に正当化するものではなく、各Sourceでresolutionが利用者側のprovider-specific codeを実際に削減できるかをfixtureとvertical sliceで継続検証します。

## 持ち運び可能な境界の判断

今回の実装では、runtime-boundな`Resource`全体をそのままJSONやIntakeへ変換する公開APIは追加しません。portableな境界は次のdomain情報です。

- `SearchResult.target`（解決先`Config`）
- `Metadata`
- `Provenance`
- `AccessPlan`のprovider非依存な値

Credential、runtime instance、`Resource._opener`はこの境界に含めません。`SearchResult`はtarget Configへ変換して別Sourceへ解決でき、解決後はアプリケーション側のResourceへ発見時のmetadata / provenanceを引き継ぎます。JSON schemaやIntake exportは、複数Sourceで情報損失と利用価値を確認してから追加します。

## 直列化／Intake出力の評価

STAC、CKANの現在のResourceを、JSON round-tripとIntakeの`driver / args / metadata`へ写す観点で比較します。

| Source | 持ち運べる解決情報 | Intakeへ写せる範囲 | 情報損失・阻害要因 |
| --- | --- | --- | --- |
| STAC | collection、item、asset、実asset URI、media type、metadata、provenance | COG等のURIを利用者が選んだraster driverへ渡せる | Intake driverはRhinestoneのExecution Adapter名と同一ではない。URIだけではasset選択理由、STAC identity、検索条件、元Itemを失う |
| CKAN | package/resource ID、配布URI、format、media type、metadata、provenance | 対応driverが既知ならfile URIと一部optionを渡せる | formatからdriverを常に決定できず、archive/encodingの対応もdriver依存。package/resourceの二段階identityとraw metadataは標準argsへ収まらない |

複数Sourceに共通するlosslessなIntake mappingは、現時点では成立しません。URIをdriver引数へ移すだけのexportは可能ですが、Rhinestoneが保持するprovider固有identity、解決理由、metadata、provenanceを失い、単なるURL passthroughになります。任意の情報をIntake metadataへ複製しても、復元規則と互換性契約がなければround-tripにはなりません。

### JSONの往復変換を追加しない理由

現在のdomain modelは、serialization schemaとして次の契約をまだ持ちません。

- `Metadata.raw`、`Provenance.raw`、`AccessPlan.options`、`Source.raw_metadata`は任意の値を保持でき、JSON型へ制限されていない
- `datetime`、tuple、frozenset、immutable mappingのJSON表現と復元規則が定義されていない
- Resourceは`Source`を内包し、同じmetadata / provenanceを重ねて保持するため、正規化した保存schemaが必要になる
- `_opener`を除外したspecificationを別のRhinestone applicationへbindする公開契約がない
- schema version、後方互換性、未知fieldの扱いが決まっていない

この状態でdataclassをそのままdictionary化するテストを追加しても、利用者が保存・転送できる安定した契約にはなりません。そのため、本評価ではserialization APIとround-tripテストを追加しません。

### 再検討条件

次を満たす具体的な利用例が現れた時点で、runtime-boundな`Resource`とは別の`ResourceSpec`を検討します。

1. 保存・転送後にResourceを再利用するconsumerとbind操作が定義されている。
2. JSONで許可する値、datetime等の表現、schema version、互換性方針が決まっている。
3. credential、runtime instance、factory、openerを含めずに再解決またはopenできる。
4. STAC、CKAN、PLATEAUの少なくとも3種で、保持する情報と意図的に捨てる情報をfixtureで比較できる。
5. Intake exportでは、既存driverへ有意味に委譲でき、Rhinestone固有のresolution情報をmetadataへ退避するだけにならない。

それまでは、`SearchResult.target`を別contextで再解決する既存経路と、解決済みResourceから専門runtimeへ直接渡す経路を維持します。Intakeとの相互運用はURLの再包装ではなく、具体的なdriver integrationが実証されたSourceから個別に再評価します。

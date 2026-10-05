# 発見と解決の検証

Issue #18 のPhase 0として、現行の主要6 Sourceを「発見結果から実行可能なResourceへ到達するまで」の観点で比較します。Rhinestoneはcatalog metadataを再収集・再ホストせず、既存のcatalog / provider APIをupstreamとして利用します。

## 比較

| Source | Discoveryで得られる情報 | resolveで補う知識 | 最終的な実行対象 | URL passthroughとの差分 |
| --- | --- | --- | --- | --- |
| CKAN / GEOSPATIAL_JP | package、resource、format、mimetype | resource metadataとpackage metadataを結合し、配布形態からAccessPlanを選ぶ | concrete file Resource | package/resourceの二段階識別とformat解釈がある |
| Search CKAN JP | dataset、resource、元catalog URL | 元catalogのResourceへ解決するための識別情報を保持する | concrete file Resource | 横断検索結果から元catalogへ戻る |
| STAC | collection、item、asset、bbox、datetime | data assetを一意に選び、COGなどのruntime要件を確定する | COGまたはvector asset | itemから実データassetを選択する |
| PLATEAU | CKAN packageと複数distribution | archive、format、CityGML entry pointを選択する | ZIP内CityGMLまたは配布file | distribution / archive memberを解釈する |
| GSI | catalog定義のtile scheme、CRS、zoom、attribution | tile access planと静的仕様を確定する | XYZ tile Resource | URLだけでなくscheme・CRS・範囲を保持する |

これらのSourceでは、少なくとも識別子・配布形態・runtimeへの引き渡し条件を解釈する責務が残ります。したがって、Rhinestoneの責務はデータ処理ではなく、次の境界に限定できます。

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

`Result.to_dict()`と`Resource.to_dict()`は、次のdomain情報をversion付きのJSON-safeな表現へ変換します。`Result.from_dict()`と`Resource.from_dict()`で復元した値はdetachedであり、resolverやopenerを持ちません。別のApplicationで利用するときは`app.bind(value)`を明示的に呼びます。

- `Result.target`（解決先`Config`）
- `Metadata`
- `Provenance`
- `AccessPlan`のprovider非依存な値

Credential、runtime instance、factory、`Result._resolver`、`Resource._opener`はこの境界に含めません。受信側ApplicationがProvider、Execution Adapter、Destination Policy、runtimeを所有します。解決後の`Resource`はtarget Sourceの`metadata` / `provenance` / `source.raw_metadata`を保持します。cross-sourceの場合は、発見側の`metadata` / `provenance` / `raw_metadata`を`Resource.discovery`へ別recordとして保持し、target側の記録を上書きしません。

```python
import json

portable = json.loads(json.dumps(result.to_dict()))
detached = Result.from_dict(portable)
result_in_another_context = another_app.bind(detached)
resource = result_in_another_context.resolve()
```

schema名は`rhinestone.result` / `rhinestone.resource`、versionは`1`です。raw mappingとoptionsは、string key、文字列、有限数、真偽値、null、配列、objectだけを受け入れます。既知のdatetime fieldはISO 8601文字列へ変換します。未知schema/versionやJSONにできない値は`ConfigValidationError`になります。既知version内の未知fieldは将来の追加fieldを古いreaderが扱えるよう読み飛ばします。

## 直列化／Intake出力の評価

STAC、CKANの現在のResourceを、JSON round-tripとIntakeの`driver / args / metadata`へ写す観点で比較します。

| Source | 持ち運べる解決情報 | Intakeへ写せる範囲 | 情報損失・阻害要因 |
| --- | --- | --- | --- |
| STAC | collection、item、asset、実asset URI、media type、metadata、provenance | COG等のURIを利用者が選んだraster driverへ渡せる | Intake driverはRhinestoneのExecution Adapter名と同一ではない。URIだけではasset選択理由、STAC identity、検索条件、元Itemを失う |
| CKAN | package/resource ID、配布URI、format、media type、metadata、provenance | 対応driverが既知ならfile URIと一部optionを渡せる | formatからdriverを常に決定できず、archive/encodingの対応もdriver依存。package/resourceの二段階identityとraw metadataは標準argsへ収まらない |

複数Sourceに共通するlosslessなIntake mappingは、現時点では成立しません。URIをdriver引数へ移すだけのexportは可能ですが、Rhinestoneが保持するprovider固有identity、解決理由、metadata、provenanceを失い、単なるURL passthroughになります。任意の情報をIntake metadataへ複製しても、復元規則と互換性契約がなければround-tripにはなりません。

### JSON往復変換の契約

portable schemaでは次の契約を固定します。

- immutable mappingとtupleはJSON object / arrayへ変換する
- Metadata / ProvenanceのdatetimeはISO 8601へ変換する
- Resourceが内包するSource、candidate、AccessPlan、discovery recordを省略せず保存する
- 復元値はdetachedとし、`app.bind()`だけが実行contextを付与する
- schema versionが未知の場合は推測せず拒否する

Intake driverへのlosslessな共通mappingは引き続き成立しないため、Intake exportは追加しません。Intakeとの相互運用はURLの再包装ではなく、具体的なdriver integrationが実証されたSourceから個別に再評価します。

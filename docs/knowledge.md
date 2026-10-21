# Knowledge Adapter（共有知識アダプター）

Rhinestoneの共有知識は、Source Adapterに直接埋め込まず、独立したKnowledge Adapterとして
注入できます。現在の対象は自治体 identity、time semantics、明示的な space value です。

```text
Source Adapter -> KnowledgeAdapterRegistry -> Identity / Time Adapter
```

## 構成

`KnowledgeAdapterDefinition`は、Source/Execution Adapter Definitionと同じくadapter type、factory、
依存関係を持ち、Knowledge種別を追加で宣言します。既定ではareaに
`japan-administrative-area`、timeに`standard-time`を使い、identityは明示選択が必要です。
独自のDefinitionは`configure(adapters=...)`で候補として登録し、
`knowledge={"種別": "adapter type"}`で利用するものを選択します。
インストールや登録だけでは既定の解釈を変更しません。同じ種別の候補を複数登録できますが、
adapter typeは組み込み・明示登録・Entry Pointsを通じて一意でなければなりません。

```python
from rhinestone import configure
from rhinestone.adapters.knowledge import KnowledgeAdapterDefinition
from rhinestone.adapters.knowledge import StandardTimeAdapter

app = configure(
    adapters=(
        KnowledgeAdapterDefinition(
            "official-municipality", make_municipality_adapter, "identity"
        ),
    ),
    knowledge={"identity": "official-municipality"},
)
```

自治体の公式辞書/APIはRhinestoneへ同梱せず、利用者のfactoryから注入します。標準Time Adapterは
追加設定なしで利用できます。factoryは検索またはSource Adapterが初めてその種別の知識を利用したときに評価されます。factoryには
`KnowledgeAdapterContext`が渡されます。

## 地域や自治体の識別（Identity）

Identity Adapterは、明示された名称またはコードを`MunicipalityIdentity`へ解決します。
Provider固有のidentifierはcanonical codeとは別に保持してください。unknown、ambiguous、
不正な入力を推測で解決してはいけません。

`StaticMunicipalityAdapter` は、利用者が供給する一つの immutable snapshot を厳密に
参照します。`MunicipalityIdentity`（行政上の identity）、`AreaCode`（コード体系と値）、
Provider projection は分離され、snapshot の `snapshot_version` は evidence として保持されます。
同名は ambiguous、辞書にない値は unknown、形式不正なコードは invalid として失敗します。

## 空間値（Space）

`BoundingBox` は axis order、範囲、明示的な `CRSRef` を持つ値オブジェクトです。既定値の
`CRS84` は既定の明示CRS識別子（`OGC:CRS84`）です。CRS識別子の構文、座標の有限性・順序、
CRS84の経緯度範囲は検証しますが、CRS定義の照会・測地変換やantimeridianの推測は行いません。
`MeshCode` は system、level、code の identity だけを保持し、geometry を導出しません。
非 `CRS84` の値を扱えるかは各 Provider の capability と projection に委ねられ、未対応なら
`unsupported` として閉じます。

## 時間の意味（Time）

Time Adapterは、暦年、年度、survey year、as-of dateを別の意味として返します。
`StandardTimeAdapter`は明示的な西暦、和暦、年度、ISO日付だけを扱います。

例えば、`令和2年`はcalendar year 2020、`2020年度`はfiscal year 2020として区別されます。
`令和元年5月1日`はas-of date 2019-05-01として扱い、元号の開始日前や次の元号開始日以後の
日付は拒否します。これはtimezone処理を行う機能ではありません。

## Source Adapterとの境界

PLATEAUと基盤地図情報のSource Adapterは、`Reference.parameters`の`municipality`と`time`を
Knowledge Adapterで解決し、返す`Resource.metadata.raw["knowledge"]`へ保持します。
identityは`["identity"]`、timeは`["time"]`に保存され、`time_kind`の明示指定も保持します。
これは現在の配信Resourceから参照する情報であり、旧候補モデルの属性ではありません。

Knowledge AdapterはProvider固有のResource選択や実データの読み込み・実行を担当しません。
共有知識を取得するための通信・依存・認証・宛先制限には、factoryへ渡される
`KnowledgeAdapterContext`のPortやcallbackを使えます。Runtime実体やCredential secretを
解決結果のmetadataに保存しません。

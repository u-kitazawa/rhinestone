# 利用インターフェース

## 基本境界

公開APIは、名前付きproviderの構成、ConfigからResourceを解決する経路、Resourceを
外部OSSへ接続する経路、SearchQueryからSearchResultを得る経路を提供します。

利用者はSource AdapterまたはExecution Adapterのinstanceを登録しません（MUST NOT）。
RhinestoneがProviderConfigとdependencyから組み込みAdapterを構成・選択します。

```python
from rhinestone import Config, ProviderConfig, configure

app = configure(
    providers={
        "gspace": ProviderConfig(
            adapter_type="ckan",
            settings={"endpoint": "https://www.geospatial.jp/ckan"},
        ),
    },
    dependencies={
        "http-json": lambda: get_json,
        "gdal": lambda: osgeo.gdal,
        "rasterio": lambda: rasterio,
    },
)
resource = app.resolve(
    Config(source_id="gspace", settings={"resource_id": "..."})
)
```

providerのmapping keyが安定した`source_id`、ProviderConfigの`adapter_type`が
解釈方式です。異なる`source_id`へ同じ`adapter_type`を割り当てられます（MUST）。

`direct` providerは常に組み込まれます。利用者定義providerで上書きできません。
未知のadapter type、空のsource id、未知のprovider optionは明示的に失敗します。

## 公開モデル

`Config`は`source_id`とprovider固有`settings`を保持します。
`SearchResult.to_config()`は同じsource idを保持して通常の解決フローへ戻します。
`Provenance.provider`にはsource id、`Provenance.adapter`にはAdapter種別を記録します。

Resource は少なくとも次へ直接アクセスできます。

```python
resource.uri
resource.metadata
resource.provenance
resource.access_plan
```

## runtime dependency

利用者は使用を許可する外部runtimeをfactoryとして供給します。組み込みExecution
Adapterは常にRhinestone側で構成され、登録済みdependencyとの互換性から選択されます。
CoreがGDAL等を直接importしてはなりません（MUST NOT）。

`http-json`はJSON API用callback、`http-text`は文書取得callback、`rdflib`は
DCAT解釈runtimeです。GIS実行には`gdal`、`rasterio`、`pyogrio`を使用します。
factoryは実際に必要になるまで評価しません。

```python
resource.open()                  # 自動選択
resource.open(adapter="gdal")    # 必要な場合だけ固定
```

`configure()`はprocess-global stateを変更せず、独立したapplication contextを返します。
同じprocess内に異なるprovider・dependency構成を共存させられます。

## credential

`credentials`はlogical nameとsecret factoryの対応です。secretをConfig、Source、
Metadata、Provenanceへ保存してはなりません（MUST NOT）。Source API認証の評価時点と
統一方法は別途credential契約で定義します。

## 戻り値

Rhinestoneは結果を共通DataFrameや独自形式へ変換しません。Execution Adapterは
外部OSSのデータ型と処理契約を尊重します。利用者はResourceを実行せず、URI、
Metadata、Provenanceだけを利用することもできます。


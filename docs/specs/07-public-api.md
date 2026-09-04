# 利用インターフェース

## 基本境界

利用インターフェースは、Config から Resource を解決する経路、Resource を外部 OSS へ接続する経路、SearchQuery から SearchResult を得る経路を提供します。

Resource は次の情報へ直接アクセスできる必要があります。

```python
resource.uri
resource.metadata
resource.provenance
```

Execution Adapter Selector が通常の実行 Adapter を選び、利用者は必要な場合だけ明示指定できます。

```python
resource.open(adapter="gdal")
```

コード例は概念的なインターフェースです。公開 API を実装するときは、[設計仕様](../spec_v4.md)のモデルと責務境界を保ちます。

## runtime dependency の供給

利用者は、使用を許可する外部 runtime を callback/factory として Dependency Registry へ供給します。

```python
rhinestone.configure(
    dependencies={
        "gdal": lambda: osgeo.gdal,
        "rasterio": lambda: rasterio,
    }
)
```

callback は lazy import、optional dependency、custom initialization、mock injection、環境固有の loading を可能にします。Core が GDAL 等を直接 import してはなりません（MUST NOT）。

## Source Adapter 基底クラス

`rhinestone.adapters.ProviderAdapter` を Source Adapter の公開基底クラスとします。
具象クラスは `source_type` を宣言し、`load(config) -> Source` を実装します。
検索はすべての Adapter に必須ではないため、基底クラスの抽象契約には含めません。

JSON ベースの組み込み Adapter は `get_json(url, params)` callback を受け取り、通信実装を利用者側から注入できるようにします。provider 固有の Config と response 解釈は具象クラスが所有します。

## 戻り値

Rhinestone はすべての結果を共通 DataFrame や独自形式へ変換しません。Execution Adapter は外部 OSS のデータ型と処理契約を尊重し、利用者は Resource を実行せず URI、Metadata、Provenance だけを利用することもできます。

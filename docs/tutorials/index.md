# 目的別チュートリアル

この章では、データ提供元の仕様を個別に学ぶのではなく、「見つけたデータを既存の専門ライブラリで使う」という目的からRhinestoneを使います。

どのチュートリアルも、次の流れを基本にしています。

```text
configure -> search -> result selection -> resolve -> Resource -> specialist runtime
```

| 目的 | 代表する解決パターン | 専門Runtime |
| --- | --- | --- |
| e-Statの人口統計表を探して利用可能なサービス情報を得る | API / identifier | なし（現行Adapterはmetadata解決まで） |
| STACから衛星画像を探して開く | Item / asset selection | Rasterio |
| PLATEAUの自治体データを探してZIP内のCityGMLを開く | distribution / archive | GDAL |

外部サービスのデータ、認証、利用条件、URLは変更される可能性があります。コードが正しくても、提供元の停止やデータの移動によって同じ結果にならない場合があります。検証可能な対象を各ページの環境変数で明示し、Rhinestoneが推測しない項目は利用者が選択します。

## 前提

```console
python -m pip install rhinestone
```

HTTP通信はRhinestoneに組み込まれています。RasterioやGDALなどのExecution Runtimeは必要なチュートリアルで別途インストールし、`configure(dependencies=...)`へ渡します。[Runtimeの導入ガイド](../runtimes.md)と[対応状況](../compatibility.md)も参照してください。

## チュートリアル

- [e-Statで人口統計表を探す](estat-population.md)
- [STACで衛星画像を探してRasterioで開く](stac-rasterio.md)
- [PLATEAUのCityGMLを探してGDALで開く](plateau-citygml.md)

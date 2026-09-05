# Rhinestone documentation

Rhinestone は、日本の公的・地理空間データに既存 OSS からアクセスするための
Python ライブラリです。配信元の API や配布形式を解釈し、読み込みライブラリへ
渡す Resource を決定します。

Rhinestone は GIS の読み込み・変換・解析を実装しません。GDAL、Rasterio、
pyogrio などの実行時ライブラリは、利用者が用意して注入します。

## はじめに

[Getting started](getting-started.md)では、インストールから Direct resource の
解決、Rasterio でデータを開くところまでを説明します。

## ガイド

- [対応状況](compatibility.md)：利用可能な provider、形式、Execution Adapter
- [サンプル集](../examples/README.md)：CKAN、e-Stat、STAC、PLATEAU、国土地理院、
  ODPT を使う実行例

## リファレンス

- [API リファレンス](api.md)：公開 API、モデル、Adapter、エラー

## 仕組み

```text
Config -> Source Adapter -> Source -> Resolver -> AccessPlan -> Resource
                                                               -> Execution Adapter -> Data
```

Source Adapter は配信元を解釈し、Resolver は使う Resource を決めます。Execution
Adapter は決定済み Resource を GDAL や Rasterio などの API 呼び出しへ変換します。
この分離により、Rhinestone はデータの取得先を判断しても、データ形式の処理を
再実装しません。

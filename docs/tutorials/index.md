# 目的別チュートリアル

ここでは、Rhinestoneを使って実際のデータを探し、利用者が用意した専門
Runtimeへ渡すまでを、目的別に説明します。基本的な流れは次のとおりです。

```text
configure -> search -> Resultを選ぶ -> resolve -> Resourceを開く
```

各チュートリアルは、異なる解決パターンを一つずつ扱います。

| 目的 | 解決パターン | 最後に得るもの |
| --- | --- | --- |
| [STAC画像をRasterioで開く](stac-rasterio.md) | Itemとdata assetを明示して選択 | Rasterioのdataset |
| [CKANのベクター配布物をpyogrioで読む](ckan-pyogrio.md) | dataset内のdistributionを選択 | GeoDataFrame相当のオブジェクト |

## 共通の注意

これらはproviderのAPIへ接続するlive tutorialです。実行にはネットワーク接続が
必要で、検索結果、配布URL、データ形式はprovider側の更新や公開状態によって変わります。
サンプルでは、URL、識別子、asset、archive memberをRhinestoneが推測しないように、
検索結果または環境変数から明示的に選択します。

Runtimeの導入方法と、Rhinestoneが保証する形式・providerの範囲は
[Runtimeの導入ガイド](../runtimes.md)と[対応状況](../compatibility.md)を参照してください。
Runtimeが返すデータの解析、形式変換、空間演算は各専門ライブラリの責務です。

外部APIの安定性や特定データセットの永続性は、RhinestoneのCIでは保証しません。
providerの仕様変更やデータの削除が疑われる場合は、まず検索結果とproviderの公式情報を
確認してください。

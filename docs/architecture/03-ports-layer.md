# Registry と依存境界仕様

> **文書ステータス: 履歴資料。** v0.4の設計を実装境界へ整理した文書で、現行APIの契約ではありません。現在の参照先は[ドキュメントの位置付け](../documentation-status.md)を確認してください。

## ［Adapter Registry］（アダプター一覧）

Source Adapter と Execution Adapter の登録状態を管理します。Registry は Core データから参照する service locator ではなく、composition 境界から調整コンポーネントへ渡します。

- 重複または矛盾する登録を黙って上書きしない（MUST NOT）。
- Source type と Source Adapter の対応を一意にする（MUST）。
- Execution Adapter の対応 Resource、access method、dependency 条件を宣言できるようにする（MUST）。
- 構築後の登録状態を決定的に扱う（MUST）。

初期実装で想定する built-in Adapter は次のとおりです。

```text
Source: CkanAdapter, StacAdapter, OgcAdapter, DirectAdapter
Execution: GdalAdapter, RasterioAdapter, PyogrioAdapter
```

一覧は実装義務ではなく、Registry が扱う代表的な分類を示します。

## ［Dependency Registry］（外部ライブラリ一覧）

利用者が所有する runtime dependency を callback/factory として管理します。

```python
dependencies = {
    "gdal": lambda: osgeo.gdal,
    "rasterio": lambda: rasterio,
}
```

- Core が runtime module を直接 import しない（MUST NOT）。
- callback は依存が必要になった時点で呼ぶ（MUST）。
- Selector は callback の登録情報から利用可能な選択肢を判断する（MUST）。
- Execution Adapter は選択済み dependency だけを取得する（MUST）。
- callback の失敗を、Resource や format の失敗と区別する（MUST）。

## 注入とテスト

両 Registry は明示的に構築・注入できなければなりません（MUST）。テストでは Source Adapter、Execution Adapter、dependency callback を小さな fake に置換し、呼び出し回数、引数、選択順序、失敗を観測できるようにします。

外部 Adapter の entry point 等は、複数の実例から安定した契約が得られた場合に設計します。

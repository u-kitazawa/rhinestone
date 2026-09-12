# 01 — URIを指定してResourceを作る

明示したURIと形式から`Resource`を作る、通信不要の例です。データをダウンロードせず、
GDALなどの外部ライブラリも必要ありません。

## 準備と実行

[uv](https://docs.astral.sh/uv/)をインストールし、リポジトリを取得して次を実行します。

```console
cd rhinestone
uv sync --dev
uv run python examples/01_direct_resource/example.py
```

URI、形式、メタデータ、出典情報が表示されます。`example.invalid`は意図的な予約ドメインで、
解決処理がデータ本体へアクセスしないことを確認できます。

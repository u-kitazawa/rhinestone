# 04 — Resourceの情報を確認する

`Resource`が単なるダウンロードURLではないことを確認する、通信不要の例です。形式、メディアタイプ、
アーカイブ、文字コード、レイヤー、メタデータ、アクセス方法、出典情報を表示します。

## 準備と実行

```console
cd rhinestone
uv sync --dev
uv run python examples/04_inspect_resource/example.py
```

ネットワーク接続やGIS用ライブラリは必要ありません。URIには予約ドメイン`example.invalid`を使い、
データ本体は開きません。

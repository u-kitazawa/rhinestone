# 06 — STACのCOGをRasterioで開く

明示したSTAC assetを解決し、利用者が用意したRasterioへ渡すlive exampleです。

## 準備と実行

```console
cd rhinestone
uv sync --dev
UV_CACHE_DIR=/tmp/rhinestone-uv-cache uv pip install rasterio
export RHINESTONE_STAC_ENDPOINT="https://your-stac.example"
export RHINESTONE_STAC_COLLECTION_ID="collection-id"
export RHINESTONE_STAC_ITEM_ID="item-id"
export RHINESTONE_STAC_ASSET_KEY="data-asset-key"
uv run python examples/06_stac_cog/example.py
```

選択したassetは、`profile=cloud-optimized`を含むCOGのメディアタイプを広告している必要があります。
`.tif`という拡張子だけからCOGとは判断しません。メタデータ取得には組み込みHTTP通信を使うため、
指定するSTAC endpointへ追加のtransport設定なしで接続できる必要があります。

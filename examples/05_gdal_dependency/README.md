# 05 — 利用者が用意したGDALで開く

利用者が用意したGDALをRhinestoneへ渡し、URIと形式を明示したデータを開く例です。
Rhinestoneは接続方法を選び、GDAL本体は利用者が用意します。

## condaを使う準備例

GDALにはネイティブライブラリが含まれるため、再現しやすい準備方法としてconda-forgeを使います。

```console
conda create -n rhinestone-gdal -c conda-forge python=3.10 gdal pip
conda activate rhinestone-gdal
cd rhinestone
python -m pip install -e .
export RHINESTONE_GDAL_URI="/absolute/path/to/data.tif"
export RHINESTONE_GDAL_FORMAT="geotiff"
python examples/05_gdal_dependency/example.py
```

リモートのZIP Shapefileを使う場合は、形式を`shapefile`にし、Configでアーカイブと文字コードを明示します。
`/vsicurl/`の利用可否はGDALのビルド方法に依存します。Rhinestone CoreがGDALをインストールしたり、
暗黙にimportしたりすることはありません。

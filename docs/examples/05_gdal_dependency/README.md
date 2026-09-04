# 05 — User-owned GDAL dependency

This example injects the user's GDAL module and explicitly opens a known local
or remote dataset. Rhinestone supplies the Adapter; the user supplies GDAL.

## Recommended setup with conda

GDAL contains native libraries, so conda-forge is the most reproducible setup:

```console
conda create -n rhinestone-gdal -c conda-forge python=3.10 gdal pip
conda activate rhinestone-gdal
cd rhinestone
python -m pip install -e .
export RHINESTONE_GDAL_URI="/absolute/path/to/data.tif"
export RHINESTONE_GDAL_FORMAT="geotiff"
python docs/examples/05_gdal_dependency/example.py
```

For a remote ZIP Shapefile, set the format to `shapefile` and describe archive
and encoding in the Config before running. Availability of `/vsicurl/` depends
on how GDAL was built. The example never installs or imports GDAL from
Rhinestone Core.


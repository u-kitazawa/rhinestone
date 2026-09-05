# GSI Tile

## Setup

Install Rhinestone and the Python bindings for GDAL. Confirm that GDAL includes
the WMS driver, then run `python examples/08_gsi_tile/example.py`.

The example opens the explicitly defined `std` XYZ tile set. Check the usage
metadata on the returned Resource before publishing a derived map.

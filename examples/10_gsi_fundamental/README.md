# GSI Fundamental Data

## Setup

Download a basic-item file from the official service, then install Rhinestone
and GDAL Python bindings. Set the `RHINESTONE_GSI_*` variables used in
`example.py` from the downloaded metadata and run
`python examples/10_gsi_fundamental/example.py`.

This example intentionally accepts only a file you have already downloaded; it
does not automate GSI login or infer CRS from a file name.

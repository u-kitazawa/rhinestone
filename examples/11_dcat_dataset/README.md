# DCAT Dataset

## Setup

Install Rhinestone, `rdflib`, and `pyogrio`. HTTP document retrieval uses Rhinestone's built-in transport. Set the three
`RHINESTONE_DCAT_*_URI` values from one DCAT catalog and run
`python examples/11_dcat_dataset/example.py`.

Choose a Distribution with a direct GeoJSON or GeoPackage `downloadURL`; a
landing page `accessURL` is metadata only and is not opened.

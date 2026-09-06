# 02 — CKAN Shapefile

This live example resolves a known G Spatial Information Center CKAN resource using `resource_show` and `package_show`. Choose a CKAN resource explicitly; the example does not guess a resource from a dataset page.

## Setup

```console
cd rhinestone
uv sync --dev
export RHINESTONE_CKAN_RESOURCE_ID="the-resource-uuid"
uv run python examples/02_ckan_shapefile/example.py
```

The CKAN endpoint comes from `sources.GEOSPATIAL_JP` in Rhinestone's source catalog and HTTP communication uses the built-in transport. Select a ZIP Shapefile resource to see archive-related access knowledge. No GDAL is needed because this example resolves metadata without opening the data.

The command performs live network requests and can fail if the provider changes or removes the resource.

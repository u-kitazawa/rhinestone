# Rhinestone Examples

Examples are ordered from resource resolution to live provider search. Run all
commands from the repository root.

| Example | Kind | What it demonstrates |
| --- | --- | --- |
| [01 Direct resource](01_direct_resource/README.md) | Deterministic | Config to Resource |
| [02 CKAN Shapefile](02_ckan_shapefile/README.md) | Live | CKAN metadata and a ZIP resource |
| [04 Inspect Resource](04_inspect_resource/README.md) | Deterministic | Knowledge retained on Resource |
| [05 GDAL dependency](05_gdal_dependency/README.md) | Runtime | User-owned GDAL and execution selection |
| [06 STAC COG](06_stac_cog/README.md) | Live/runtime | STAC asset to Rasterio |
| [07 Search and fetch](07_search_and_fetch/README.md) | Live/demo | Single-source search back through Config |

Base setup:

```console
git clone <repository-url> rhinestone
cd rhinestone
uv sync --dev
```

Examples never infer provider, format, asset, or resource identifiers. Live
values are environment variables so users can select a resource whose terms and
availability they have verified.

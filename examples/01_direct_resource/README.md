# 01 — Direct resource

This deterministic example resolves an explicitly described resource. It does
not download data and does not require a GIS runtime.

## Setup

Install [uv](https://docs.astral.sh/uv/), clone the repository, and run:

```console
cd rhinestone
uv sync --dev
uv run python docs/examples/01_direct_resource/example.py
```

The output shows the URI, format, Metadata, and Provenance. The
`example.invalid` URI is intentional: resolution must not perform dataset I/O.


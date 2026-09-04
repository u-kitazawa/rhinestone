# 04 — Inspect a Resource

This deterministic example demonstrates why a Rhinestone Resource is more than
a download URL. It displays format, media type, archive, encoding, layer,
Metadata, Source, AccessPlan, and Provenance.

## Setup and run

```console
cd rhinestone
uv sync --dev
uv run python docs/examples/04_inspect_resource/example.py
```

No network or GIS runtime is required. The URI uses the reserved
`example.invalid` domain and is never opened.


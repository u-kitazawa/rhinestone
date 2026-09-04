# 03 — e-Stat population metadata

This live example resolves an e-Stat statistical table into a service-query
Resource while retaining its metadata and provenance.

## Setup

1. Register for an application ID on the
   [e-Stat API site](https://www.e-stat.go.jp/api/).
2. Find a population table and copy its `statsDataId`.
3. Run:

```console
cd rhinestone
uv sync --dev
export RHINESTONE_ESTAT_APP_ID="your-application-id"
# Alternatively: export RHINESTONE_ESTAT_API_KEY="your-application-id"
export RHINESTONE_ESTAT_STATS_DATA_ID="your-current-stats-data-id"
uv run python docs/examples/03_estat_population/example.py
```

Use the `statsDataId` from a currently available table in e-Stat search results;
the government statistics code (`statsCode`) is a different value. The
application ID/API key is supplied as the official `appId` query parameter and
is not stored in Provenance.
This example resolves metadata; fetching statistical values is a later execution
slice. The command requires network access to e-Stat API 3.0.

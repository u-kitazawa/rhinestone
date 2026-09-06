"""Search built-in CKAN and e-Stat sources, then resolve a selected result."""

import os
import sys
from pathlib import Path

from rhinestone import SearchQuery, configure, sources

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _support.http_json import get_json  # noqa: E402

estat_key = (
    os.environ.get("RHINESTONE_ESTAT_APP_ID") or os.environ["RHINESTONE_ESTAT_API_KEY"]
)
app = configure(
    sources=(sources.GEOSPATIAL_JP, sources.ESTAT),
    dependencies={"http-json": lambda: get_json},
    credentials={"estat": lambda: estat_key},
)
grouped = app.search(
    SearchQuery(text=os.environ.get("RHINESTONE_QUERY", "人口"), limit=3)
)

for source_id, results in grouped.items():
    print(source_id)
    for index, result in enumerate(results):
        print(f"  [{index}] {result.title}")

source_id = os.environ.get("RHINESTONE_RESULT_SOURCE", "estat")
selected = grouped[source_id][0]
resource = app.resolve(selected.to_config())
print("selected resource:", resource.uri)
print("metadata:", resource.metadata)
print("provenance:", resource.provenance)

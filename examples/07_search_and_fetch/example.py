"""Search built-in CKAN and e-Stat sources, then resolve a selected result."""

import os

from rhinestone import SearchQuery, configure, sources

estat_key = (
    os.environ.get("RHINESTONE_ESTAT_APP_ID") or os.environ["RHINESTONE_ESTAT_API_KEY"]
)
app = configure(
    sources=(sources.GEOSPATIAL_JP, sources.ESTAT),
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
resource = selected.resolve()
print("selected resource:", resource.uri)
print("metadata:", resource.metadata)
print("provenance:", resource.provenance)

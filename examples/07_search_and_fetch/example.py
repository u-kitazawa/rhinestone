"""Search the built-in CKAN source, then resolve a selected result."""

import os

from rhinestone import SearchQuery, configure, sources

app = configure(sources=(sources.GEOSPATIAL_JP,))
grouped = app.search(
    SearchQuery(text=os.environ.get("RHINESTONE_QUERY", "人口"), limit=3)
)

for source_id, results in grouped.items():
    print(source_id)
    for index, result in enumerate(results):
        print(f"  [{index}] {result.title}")

source_id = "geospatial-jp"
selected = grouped[source_id][0]
resource = selected.resolve()
print("selected resource:", resource.uri)
print("metadata:", resource.metadata)
print("provenance:", resource.provenance)

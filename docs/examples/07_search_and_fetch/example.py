"""Search CKAN and e-Stat, then resolve a selected result normally."""

import os
import sys
from pathlib import Path

from rhinestone import SearchQuery, configure
from rhinestone.adapters import CkanAdapter, EStatAdapter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _support.http_json import get_json  # noqa: E402

ckan_kwargs = {"get_json": get_json}
if os.environ.get("RHINESTONE_CKAN_API_TOKEN"):
    ckan_kwargs["api_token"] = os.environ["RHINESTONE_CKAN_API_TOKEN"]
elif os.environ.get("RHINESTONE_CKAN_API_KEY"):
    ckan_kwargs["api_key"] = os.environ["RHINESTONE_CKAN_API_KEY"]
ckan = CkanAdapter(endpoint=os.environ["RHINESTONE_CKAN_ENDPOINT"], **ckan_kwargs)
estat_key = (
    os.environ.get("RHINESTONE_ESTAT_APP_ID") or os.environ["RHINESTONE_ESTAT_API_KEY"]
)
estat = EStatAdapter(api_key=estat_key, get_json=get_json)
app = configure(
    dependencies={},
    source_adapters=(ckan, estat),
    execution_adapters=(),
)
grouped = app.search(
    SearchQuery(text=os.environ.get("RHINESTONE_QUERY", "人口"), limit=3)
)

for provider, results in grouped.items():
    print(provider)
    for index, result in enumerate(results):
        print(f"  [{index}] {result.title}")

provider = os.environ.get("RHINESTONE_RESULT_PROVIDER", "estat")
selected = grouped[provider][0]
resource = app.resolve(selected.to_config())
print("selected resource:", resource.uri)
print("metadata:", resource.metadata)
print("provenance:", resource.provenance)

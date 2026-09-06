"""Search CKAN and e-Stat, then resolve a selected result normally."""

import os
import sys
from pathlib import Path

from rhinestone import ProviderConfig, SearchQuery, configure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _support.http_json import get_json  # noqa: E402

ckan_settings = {"endpoint": os.environ["RHINESTONE_CKAN_ENDPOINT"]}
if os.environ.get("RHINESTONE_CKAN_API_TOKEN"):
    ckan_settings["api_token"] = os.environ["RHINESTONE_CKAN_API_TOKEN"]
elif os.environ.get("RHINESTONE_CKAN_API_KEY"):
    ckan_settings["api_key"] = os.environ["RHINESTONE_CKAN_API_KEY"]
estat_key = (
    os.environ.get("RHINESTONE_ESTAT_APP_ID") or os.environ["RHINESTONE_ESTAT_API_KEY"]
)
app = configure(
    providers={
        "open-data": ProviderConfig("ckan", ckan_settings),
        "estat": ProviderConfig("estat", {"api_key": estat_key}),
    },
    dependencies={"http-json": lambda: get_json},
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

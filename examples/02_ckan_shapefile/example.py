"""Resolve one explicitly selected CKAN resource through the Action API."""

import os
import sys
from pathlib import Path

from rhinestone import Config, configure
from rhinestone.adapters import CkanAdapter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _support.http_json import get_json  # noqa: E402

endpoint = os.environ["RHINESTONE_CKAN_ENDPOINT"]
resource_id = os.environ["RHINESTONE_CKAN_RESOURCE_ID"]
adapter_kwargs = {"get_json": get_json}
if os.environ.get("RHINESTONE_CKAN_API_TOKEN"):
    adapter_kwargs["api_token"] = os.environ["RHINESTONE_CKAN_API_TOKEN"]
elif os.environ.get("RHINESTONE_CKAN_API_KEY"):
    adapter_kwargs["api_key"] = os.environ["RHINESTONE_CKAN_API_KEY"]
app = configure(
    dependencies={},
    source_adapters=(CkanAdapter(endpoint=endpoint, **adapter_kwargs),),
    execution_adapters=(),
)
resource = app.resolve(
    Config(
        source_type="ckan",
        settings={"endpoint": endpoint, "resource_id": resource_id},
    )
)

print("URI:", resource.uri)
print("format:", resource.format)
print("metadata:", resource.metadata)
print("access plan:", resource.access_plan)
print("provenance:", resource.provenance)

"""Resolve one explicitly selected CKAN resource through the Action API."""

import os
import sys
from pathlib import Path

from rhinestone import Config, ProviderConfig, configure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _support.http_json import get_json  # noqa: E402

endpoint = os.environ["RHINESTONE_CKAN_ENDPOINT"]
resource_id = os.environ["RHINESTONE_CKAN_RESOURCE_ID"]
provider_settings = {"endpoint": endpoint}
if os.environ.get("RHINESTONE_CKAN_API_TOKEN"):
    provider_settings["api_token"] = os.environ["RHINESTONE_CKAN_API_TOKEN"]
elif os.environ.get("RHINESTONE_CKAN_API_KEY"):
    provider_settings["api_key"] = os.environ["RHINESTONE_CKAN_API_KEY"]
app = configure(
    providers={"gspace": ProviderConfig("ckan", provider_settings)},
    dependencies={"http-json": lambda: get_json},
)
resource = app.resolve(
    Config(
        source_id="gspace",
        settings={"resource_id": resource_id},
    )
)

print("URI:", resource.uri)
print("format:", resource.format)
print("metadata:", resource.metadata)
print("access plan:", resource.access_plan)
print("provenance:", resource.provenance)

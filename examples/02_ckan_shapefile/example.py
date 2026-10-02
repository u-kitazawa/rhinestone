"""Resolve one explicitly selected G Spatial Information Center CKAN resource."""

import os

from rhinestone import Config, configure
from rhinestone.catalogs import BUILTIN, Catalog

resource_id = os.environ["RHINESTONE_CKAN_RESOURCE_ID"]
app = configure(
    catalog=Catalog(provider for provider in BUILTIN if provider.id == "geospatial-jp")
)
resource = app.resolve(
    Config(
        source_id="geospatial-jp",
        settings={"resource_id": resource_id},
    )
)

print("URI:", resource.uri)
print("format:", resource.format)
print("metadata:", resource.metadata)
print("access plan:", resource.access_plan)
print("provenance:", resource.provenance)

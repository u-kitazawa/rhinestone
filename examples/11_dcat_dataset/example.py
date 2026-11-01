"""Resolve a DCAT Dataset distribution and open it with user-owned pyogrio."""

import os

import pyogrio
import rdflib

from rhinestone import Provider, Reference, configure
from rhinestone.catalogs import Catalog
from rhinestone.models import RuntimeFactory

catalog_uri = os.environ["RHINESTONE_DCAT_URI"]
app = configure(
    catalog=Catalog((Provider("catalog", "dcat", {"catalog_uri": catalog_uri}),)),
    dependencies={
        "rdflib": RuntimeFactory(lambda: rdflib),
    },
)
resource = app.load(
    Reference(
        "catalog",
        parameters={
            "uri": catalog_uri,
            "dataset": os.environ["RHINESTONE_DCAT_DATASET_URI"],
            "distribution": os.environ["RHINESTONE_DCAT_DISTRIBUTION_URI"],
            "serialization": os.environ.get("RHINESTONE_DCAT_SERIALIZATION", "turtle"),
        },
    )
)
frame = resource.open("pyogrio", runtime=pyogrio)
print("URI:", resource.uri)
print("provenance:", resource.provenance)
print("rows:", len(frame))

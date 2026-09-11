"""Resolve a DCAT Dataset distribution and open it with user-owned pyogrio."""

import os

import pyogrio
import rdflib

from rhinestone import Config, RuntimeFactory, SourceDefinition, configure

catalog_uri = os.environ["RHINESTONE_DCAT_URI"]
app = configure(
    sources=(SourceDefinition("catalog", "dcat", {"catalog_uri": catalog_uri}),),
    dependencies={
        "rdflib": RuntimeFactory(lambda: rdflib),
        "pyogrio": RuntimeFactory(lambda: pyogrio),
    },
)
resource = app.resolve(
    Config(
        "catalog",
        {
            "uri": catalog_uri,
            "dataset": os.environ["RHINESTONE_DCAT_DATASET_URI"],
            "distribution": os.environ["RHINESTONE_DCAT_DISTRIBUTION_URI"],
            "serialization": os.environ.get("RHINESTONE_DCAT_SERIALIZATION", "turtle"),
        },
    )
)
frame = resource.open("pyogrio")
print("URI:", resource.uri)
print("provenance:", resource.provenance)
print("rows:", len(frame))

"""Resolve a DCAT Dataset distribution and open it with user-owned pyogrio."""

import os

import pyogrio
import rdflib
import requests

from rhinestone import Config, ProviderConfig, configure


def get_document(uri):
    return requests.get(uri, timeout=30).text


app = configure(
    providers={
        "catalog": ProviderConfig(
            "dcat", {"catalog_uri": os.environ["RHINESTONE_DCAT_URI"]}
        )
    },
    dependencies={
        "http-text": lambda: get_document,
        "rdflib": lambda: rdflib,
        "pyogrio": lambda: pyogrio,
    },
)
resource = app.resolve(
    Config(
        "catalog",
        {
            "uri": os.environ["RHINESTONE_DCAT_URI"],
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

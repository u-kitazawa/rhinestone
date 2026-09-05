"""Resolve a DCAT Dataset distribution and open it with user-owned pyogrio."""

import os

import pyogrio
import rdflib
import requests

from rhinestone import Config, configure
from rhinestone.adapters import DcatAdapter
from rhinestone.execution_adapters import PyogrioAdapter


def get_document(uri):
    return requests.get(uri, timeout=30).text


app = configure(
    dependencies={"pyogrio": lambda: pyogrio},
    source_adapters=(
        DcatAdapter(
            get_document,
            lambda: rdflib,
            os.environ["RHINESTONE_DCAT_URI"],
        ),
    ),
    execution_adapters=(PyogrioAdapter(),),
)
resource = app.resolve(
    Config(
        "dcat",
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

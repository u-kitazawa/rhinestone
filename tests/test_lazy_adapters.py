"""Cold-process checks prevent test collection from hiding eager imports."""

import subprocess
import sys
from importlib import import_module

import pytest


@pytest.mark.parametrize(
    "package",
    (
        "rhinestone.adapters",
        "rhinestone.adapters.provider",
        "rhinestone.adapters.runtime",
        "rhinestone.adapters.knowledge",
    ),
)
def test_public_exports_are_resolvable_and_unknown_names_raise_attribute_error(
    package: str,
) -> None:
    module = import_module(package)
    for name in module.__all__:
        value = getattr(module, name)
        assert value is getattr(module, name)
    with pytest.raises(AttributeError, match="missing_export"):
        getattr(module, "missing_export")


def test_cold_application_loads_only_selected_builtin_implementations() -> None:
    script = """
import sys
from types import SimpleNamespace
from rhinestone import Catalog, Provider, Reference, configure
from rhinestone.adapters.contracts import ProviderAdapterDefinition

assert not any(name.startswith("rhinestone.adapters.provider") for name in sys.modules)
assert not any(name.startswith("rhinestone.adapters.runtime") for name in sys.modules)
assert "rhinestone.adapters.knowledge.time" not in sys.modules
assert "rhinestone.adapters.knowledge.area" not in sys.modules
assert "rhinestone.adapters.knowledge._japan_administrative_areas" not in sys.modules

configure()
assert "rhinestone.adapters.provider.direct.adapter" in sys.modules
assert not any(name.startswith("rhinestone.adapters.runtime") for name in sys.modules)
assert "rhinestone.adapters.knowledge.time" not in sys.modules
assert "rhinestone.adapters.knowledge.area" not in sys.modules

from rhinestone.adapters.provider.direct import DirectAdapter
ports = []
def capture(provider, context):
    ports.append(context.knowledge)
    return DirectAdapter()

app = configure(
    catalog=Catalog((Provider("chosen", "stac", {"endpoint":"https://fixture.example"}),
                     Provider("capture", "capture"))),
    adapters=(ProviderAdapterDefinition("capture", capture),),
)
assert "rhinestone.adapters.provider.stac.adapter" in sys.modules
for name in ("ckan", "dcat", "estat_gis", "geospatial_jp", "gsi_fundamental",
             "mlit_dpf", "odpt", "ogc", "plateau", "search_ckan_jp", "static"):
    assert "rhinestone.adapters.provider." + name not in sys.modules, name
assert "rhinestone.adapters.knowledge.time" not in sys.modules
assert ports[0].resolve_time("2020").year == 2020
assert "rhinestone.adapters.knowledge.time" in sys.modules
assert "rhinestone.adapters.knowledge.area" not in sys.modules
assert ports[0].resolve_area("東京都").canonical_name == "東京都"
assert "rhinestone.adapters.knowledge.area" in sys.modules

resource = app.load(Reference("direct", parameters={
    "uri":"https://fixture.example/one.tif", "format":"geotiff"
}))
plan = app.plan(resource)
assert not any(name.startswith("rhinestone.adapters.runtime") for name in sys.modules)
assert app.open(plan, "rasterio", runtime=SimpleNamespace(open=lambda uri:uri)) == plan.uri
assert "rhinestone.adapters.runtime.rasterio.adapter" in sys.modules
for name in ("gdal", "pyogrio", "json_service"):
    assert "rhinestone.adapters.runtime." + name not in sys.modules, name
assert not {"rasterio", "osgeo", "pyogrio", "rdflib"}.intersection(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr

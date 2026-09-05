import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import pytest

EXAMPLES_ROOT = Path(__file__).parents[1] / "examples"
EXAMPLE_NAMES: Tuple[str, ...] = (
    "01_direct_resource",
    "02_ckan_shapefile",
    "03_estat_population",
    "04_inspect_resource",
    "05_gdal_dependency",
    "06_stac_cog",
    "07_search_and_fetch",
    "08_gsi_tile",
    "09_plateau_citygml",
    "10_gsi_fundamental",
    "11_dcat_dataset",
    "12_odpt_station",
)


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_each_example_has_runnable_code_and_setup_readme(name: str) -> None:
    """利用者が各Exampleを単独で見ても環境構築と実行方法を再現できるようにするために必要である。"""
    directory = EXAMPLES_ROOT / name
    script = directory / "example.py"
    readme = directory / "README.md"

    assert script.is_file()
    assert readme.is_file()
    instructions = readme.read_text(encoding="utf-8").lower()
    assert "setup" in instructions
    assert "python" in instructions


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_every_example_script_compiles(name: str) -> None:
    """任意dependencyやcredentialがないCIでも全ExampleのPython互換性を検証するために必要である。"""
    script = EXAMPLES_ROOT / name / "example.py"

    compile(script.read_text(encoding="utf-8"), str(script), "exec")


@pytest.mark.parametrize("name", ("01_direct_resource", "04_inspect_resource"))
def test_deterministic_examples_run_without_network_or_optional_runtime(
    name: str,
) -> None:
    """最初の学習用Exampleが追加環境なしで実際に最後まで動作することを保証するために必要である。"""
    script = EXAMPLES_ROOT / name / "example.py"

    completed = subprocess.run(
        [sys.executable, str(script)],
        check=True,
        capture_output=True,
        text=True,
        cwd=EXAMPLES_ROOT.parent,
    )

    assert "URI:" in completed.stdout
    assert "provenance:" in completed.stdout


def test_service_examples_use_formats_known_to_create_service_plans() -> None:
    """e-StatとOGC Exampleが誤ってFileAccessPlanへ解決される退行を防ぐために必要である。"""
    from rhinestone.models import Metadata, Provenance, ResourceCandidate, Source
    from rhinestone.resolution import Resolver

    for format_name in ("estat-api", "ogc-api-features"):
        candidate = ResourceCandidate("https://api.example/data", format_name, None)
        source = Source(
            metadata=Metadata(raw={}),
            candidates=(candidate,),
            capabilities=frozenset({"service-query"}),
            provenance=Provenance(provider="fixture", raw={}),
            raw_metadata={},
        )
        assert Resolver().resolve(source).access_plan.kind == "service-query"


@pytest.mark.parametrize(
    "name",
    ("02_ckan_shapefile", "03_estat_population", "07_search_and_fetch"),
)
def test_live_examples_import_shared_transport_when_run_by_file_path(
    name: str,
) -> None:
    """README記載のfile-path起動で共有HTTP transportのimportに失敗しないために必要である。"""
    script = EXAMPLES_ROOT / name / "example.py"
    environment = dict(os.environ)
    for key in tuple(environment):
        if key.startswith("RHINESTONE_"):
            del environment[key]

    completed = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=EXAMPLES_ROOT.parent,
        env=environment,
    )

    assert completed.returncode != 0
    assert "RHINESTONE_" in completed.stderr
    assert "ModuleNotFoundError" not in completed.stderr

import pytest

from rhinestone.adapters.source.direct import DirectAdapter
from rhinestone.errors import ConfigValidationError
from rhinestone.models import Config, Reference


def test_direct_adapter_preserves_explicit_resource_knowledge() -> None:
    """公式direct URIをprovider通信なしでSourceへ変換し、利用者が示した知識を保持するために必要である。"""
    config = Config(
        source_id="direct",
        settings={
            "uri": "https://files.example/rivers.zip",
            "format": "shapefile",
            "media_type": "application/zip",
            "archive": "zip",
            "encoding": "cp932",
            "metadata": {"title": "Rivers", "publisher": "River Agency"},
        },
    )

    source = DirectAdapter().load(Reference.from_config(config))

    assert source.metadata.title == "Rivers"
    assert source.metadata.publisher == "River Agency"
    assert source.uri == "https://files.example/rivers.zip"
    assert source.format == "shapefile"
    assert source.access_plan is not None
    assert source.access_plan.options["archive"] == "zip"
    assert source.access_plan.options["encoding"] == "cp932"
    assert source.provenance.provider == "direct"
    assert source.provenance.original_url == "https://files.example/rivers.zip"
    assert source.provenance.raw == config.settings


@pytest.mark.parametrize("missing", ("uri", "format"))
def test_direct_adapter_requires_uri_and_format(missing: str) -> None:
    """URL suffixからURIやformatを推測せず、不足した宣言を明示的に失敗させるために必要である。"""
    settings = {
        "uri": "https://files.example/rivers.geojson",
        "format": "geojson",
    }
    del settings[missing]

    with pytest.raises(ConfigValidationError, match=missing):
        DirectAdapter().load(
            Reference.from_config(Config(source_id="direct", settings=settings))
        )


def test_direct_adapter_rejects_runtime_and_transport_details() -> None:
    """宣言的ConfigへGDAL instanceやHTTP実装詳細が混入するのを防ぐために必要である。"""
    config = Config(
        source_id="direct",
        settings={
            "uri": "https://files.example/rivers.geojson",
            "format": "geojson",
            "gdal": object(),
        },
    )

    with pytest.raises(ConfigValidationError, match="gdal"):
        DirectAdapter().load(Reference.from_config(config))


def test_direct_adapter_rejects_non_object_metadata() -> None:
    """構造不正の利用者metadataをraw knowledgeとして取り込まないために必要である。"""
    config = Config(
        source_id="direct",
        settings={"uri": "/data/a.csv", "format": "csv", "metadata": "invalid"},
    )

    with pytest.raises(ConfigValidationError, match="metadata"):
        DirectAdapter().load(Reference.from_config(config))

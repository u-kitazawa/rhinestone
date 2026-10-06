from datetime import datetime

import pytest

import rhinestone
import rhinestone.api as api  # pyright: ignore[reportPrivateUsage]
from rhinestone import Catalog, Provider, configure
from rhinestone.catalogs import BUILTIN
from rhinestone.search import SearchResults


def test_standard_application_is_lazy_cached_and_uses_builtin_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: list[Catalog] = []
    calls: list[tuple[object, dict[str, object]]] = []
    expected = SearchResults.from_grouped({})

    class FakeApplication:
        def __init__(self, *, catalog: Catalog) -> None:
            constructed.append(catalog)

        def search(self, query: object = None, **kwargs: object) -> SearchResults:
            calls.append((query, kwargs))
            return expected

    api._default_application.cache_clear()  # pyright: ignore[reportPrivateUsage]
    assert api._default_application.cache_info().currsize == 0  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(api, "Rhinestone", FakeApplication)
    try:
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        assert (
            rhinestone.search(
                "river",
                area=None,
                bbox=(139.0, 35.0, 140.0, 36.0),
                time=(start, end),
                limit=3,
            )
            is expected
        )
        assert rhinestone.search(text="road") is expected
    finally:
        api._default_application.cache_clear()  # pyright: ignore[reportPrivateUsage]

    assert constructed == [BUILTIN]
    assert calls == [
        (
            "river",
            {
                "text": None,
                "area": None,
                "bbox": (139.0, 35.0, 140.0, 36.0),
                "time": (start, end),
                "format": None,
                "limit": 3,
                "providers": None,
            },
        ),
        (
            None,
            {
                "text": "road",
                "area": None,
                "bbox": None,
                "time": None,
                "format": None,
                "limit": None,
                "providers": None,
            },
        ),
    ]


def test_top_level_result_resolves_with_its_standard_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = configure(
        catalog=Catalog(
            (
                Provider(
                    "gsi",
                    "static",
                    {
                        "items": {
                            "standard": {
                                "metadata": {"title": "Standard map"},
                                "candidates": [
                                    {
                                        "uri": "https://example.test/{z}/{x}/{y}.png",
                                        "format": "xyz-tiles",
                                        "media_type": "image/png",
                                    }
                                ],
                                "capabilities": ["remote-dataset", "search"],
                            },
                        }
                    },
                ),
            )
        )
    )
    monkeypatch.setattr(api, "_default_application", lambda: application)

    result = rhinestone.search(text="Standard", limit=1)[0]
    resource = result.resolve()

    assert resource.uri == "https://example.test/{z}/{x}/{y}.png"
    assert resource.provenance.provider == "gsi"


def test_configure_does_not_replace_the_standard_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    standard = configure(catalog=Catalog(()))
    monkeypatch.setattr(api, "_default_application", lambda: standard)

    custom = configure(
        catalog=Catalog(
            (
                Provider(
                    "custom",
                    "static",
                    {
                        "items": {
                            "custom": {
                                "metadata": {"title": "Custom"},
                                "candidates": [
                                    {
                                        "uri": "https://example.test/custom.csv",
                                        "format": "csv",
                                        "media_type": "text/csv",
                                    }
                                ],
                                "capabilities": ["remote-dataset", "search"],
                            }
                        }
                    },
                ),
            )
        )
    )

    assert custom is not standard
    assert rhinestone.search("missing") is not custom.search("missing")

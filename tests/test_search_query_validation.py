from typing import Any, cast

import pytest

import rhinestone._http as _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import configure, search
from rhinestone.catalogs import Catalog
from rhinestone.errors import ConfigValidationError
from rhinestone.models import SearchQuery


def test_search_query_rejects_non_string_text() -> None:
    with pytest.raises(ConfigValidationError, match="text must be a string or None"):
        SearchQuery(text=cast(Any, 1))


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_search_query_rejects_explicit_blank_text(text: str) -> None:
    with pytest.raises(
        ConfigValidationError,
        match="text must be a non-empty string or None",
    ):
        SearchQuery(text=text)


def test_search_query_rejects_invalid_limit_without_repr() -> None:
    class SecretLimit:
        def __repr__(self) -> str:
            raise AssertionError("__repr__ must not be called")

    with pytest.raises(ConfigValidationError) as error:
        SearchQuery(limit=cast(Any, SecretLimit()))

    assert "limit must be a non-negative integer" in str(error.value)
    assert "SecretLimit" in str(error.value)


def test_app_search_rejects_non_string_text_before_search_dispatch() -> None:
    app = configure(catalog=Catalog(()))

    with pytest.raises(ConfigValidationError, match="text must be a string or None"):
        app.search(text=cast(Any, 1))


@pytest.mark.parametrize("query", ["", "   "])
def test_app_search_rejects_explicit_blank_text_before_search_dispatch(
    query: str,
) -> None:
    app = configure(catalog=Catalog(()))

    with pytest.raises(
        ConfigValidationError,
        match="text must be a non-empty string or None",
    ):
        app.search(query)

    with pytest.raises(
        ConfigValidationError,
        match="text must be a non-empty string or None",
    ):
        app.search(text=query)


def test_search_query_accepts_non_empty_string_and_unspecified_text() -> None:
    assert SearchQuery(text="river").text == "river"
    assert SearchQuery(text=None).text is None
    assert SearchQuery().supplied_conditions == frozenset()


@pytest.mark.parametrize("query", [123, True, [], {}, object()])
def test_public_search_rejects_invalid_query_before_network(
    monkeypatch: pytest.MonkeyPatch, query: object
) -> None:
    def no_request(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("invalid query must not request Provider data")

    monkeypatch.setattr(_http, "get_json", no_request)
    app = configure()
    for run_search in (app.search, search):
        with pytest.raises(ConfigValidationError, match="query must be"):
            run_search(query=cast(Any, query))


def test_invalid_query_validation_does_not_inspect_user_object() -> None:
    class SecretQuery:
        def __repr__(self) -> str:
            raise AssertionError("query repr must not be called")

        @property
        def providers(self) -> None:
            raise AssertionError("query attributes must not be accessed")

    with pytest.raises(ConfigValidationError, match="query must be"):
        configure().search(cast(Any, SecretQuery()))

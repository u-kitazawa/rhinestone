from typing import Any, cast

import pytest

from rhinestone import configure
from rhinestone.errors import ConfigValidationError
from rhinestone.models import SearchQuery


def test_search_query_rejects_non_string_text() -> None:
    with pytest.raises(ConfigValidationError, match="text must be a string or None"):
        SearchQuery(text=cast(Any, 1))


def test_search_query_rejects_invalid_limit_without_repr() -> None:
    class SecretLimit:
        def __repr__(self) -> str:
            raise AssertionError("__repr__ must not be called")

    with pytest.raises(ConfigValidationError) as error:
        SearchQuery(limit=cast(Any, SecretLimit()))

    assert "limit must be a non-negative integer" in str(error.value)
    assert "SecretLimit" in str(error.value)


def test_app_search_rejects_non_string_text_before_search_dispatch() -> None:
    app = configure(sources=())

    with pytest.raises(ConfigValidationError, match="text must be a string or None"):
        app.search(text=cast(Any, 1))


def test_search_query_accepts_string_and_none_text() -> None:
    assert SearchQuery(text="river").text == "river"
    assert SearchQuery(text=None).text is None

from typing import Any, cast

import pytest

from rhinestone import AccessPlan, Reference, configure
from rhinestone.errors import ConfigValidationError


class InvalidBindValue:
    @property
    def access_plan(self) -> object:
        raise AssertionError("invalid value attributes must not be read")

    def __str__(self) -> str:
        raise AssertionError("invalid value must not be stringified")

    def __repr__(self) -> str:
        raise AssertionError("invalid value must not be represented")


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        "secret-input",
        {},
        [],
        object(),
        Reference("direct"),
        AccessPlan(kind="file", uri="https://example.test/data.tif", format="geotiff"),
        InvalidBindValue(),
    ],
    ids=[
        "none",
        "integer",
        "string",
        "mapping",
        "list",
        "object",
        "reference",
        "plan",
        "hostile",
    ],
)
def test_bind_rejects_non_resource_without_inspecting_its_value(value: object) -> None:
    app = configure()

    with pytest.raises(ConfigValidationError) as raised:
        app.bind(cast(Any, value))

    assert str(raised.value) == "bind value must be a Resource"

"""Validate Provider identifiers before composition or external access."""

from typing import Any

import pytest

from rhinestone import Provider, ProviderId
from rhinestone.errors import ConfigValidationError


@pytest.mark.parametrize("field", ("id", "adapter_type"))
@pytest.mark.parametrize(
    "value",
    (None, 123, False, ["secret"], {"secret": "value"}, object(), "", "   "),
    ids=("none", "number", "boolean", "list", "mapping", "object", "empty", "blank"),
)
def test_provider_rejects_invalid_identifiers(field: str, value: Any) -> None:
    values: dict[str, Any] = {"id": "example", "adapter_type": "direct"}
    values[field] = value

    with pytest.raises(ConfigValidationError) as raised:
        Provider(**values)

    assert "must be a non-empty string" in str(raised.value)
    assert "secret" not in str(raised.value)


def test_provider_preserves_valid_string_identifiers() -> None:
    provider = Provider(ProviderId.GSI, "static")

    assert provider.id is ProviderId.GSI
    assert provider.adapter_type == "static"

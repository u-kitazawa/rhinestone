"""Provider settings must be a mapping before any Adapter interprets them."""

from typing import Any

import pytest

from rhinestone import Provider
from rhinestone.errors import ConfigValidationError


@pytest.mark.parametrize(
    "settings",
    (None, False, 123, "secret-settings", [], (), object()),
    ids=("none", "boolean", "number", "string", "list", "tuple", "object"),
)
def test_provider_rejects_non_mapping_settings(settings: Any) -> None:
    with pytest.raises(ConfigValidationError) as raised:
        Provider("example", "stac", settings)

    assert str(raised.value) == "Provider.settings must be a mapping"


def test_provider_settings_keep_detached_immutable_mapping_contract() -> None:
    values = {"filters": {"collections": ["example"]}}
    provider = Provider("example", "stac", values)
    values["filters"]["collections"].append("changed")

    assert provider.settings["filters"]["collections"] == ("example",)
    with pytest.raises(TypeError):
        provider.settings["filters"]["collections"] = ("changed",)

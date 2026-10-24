"""Extensions use one vocabulary without compatibility aliases."""

from importlib import import_module
from importlib.util import find_spec

import pytest


def test_retired_adapter_packages_are_not_installed() -> None:
    for name in (
        "rhinestone.adapters.source",
        "rhinestone.adapters.execution",
        "rhinestone.execution",
    ):
        assert find_spec(name) is None


def test_retired_adapter_contracts_and_errors_are_not_aliases() -> None:
    contracts = import_module("rhinestone.adapters.contracts")
    for name in (
        "SourceAdapter",
        "SearchableSourceAdapter",
        "SourceAdapterContext",
        "SourceAdapterDefinition",
        "SourceAdapterFactory",
        "ExecutionAdapter",
        "ExecutionAdapterContext",
        "ExecutionAdapterDefinition",
        "ExecutionAdapterFactory",
    ):
        with pytest.raises(AttributeError):
            getattr(contracts, name)
    errors = import_module("rhinestone.errors")
    for name in ("ExecutionAdapterUnavailableError", "UnsupportedSourceError"):
        with pytest.raises(AttributeError):
            getattr(errors, name)

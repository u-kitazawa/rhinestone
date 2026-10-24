"""An unused plugin must not import its missing optional dependency."""

from importlib import import_module

import_module("rhinestone_deliberately_absent_optional_dependency")
definition = object()

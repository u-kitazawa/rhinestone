"""Application pipeline from Config through Source to Resource."""

from typing import Any, Iterable

from .errors import ProviderMetadataError, RhinestoneError, UnsupportedSourceError
from .models import Config, Resource
from .resolution import Resolver


class AccessPipeline:
    def __init__(self, source_adapters: Iterable[Any], resolver: Resolver) -> None:
        self._source_adapters = tuple(source_adapters)
        self._resolver = resolver

    def resolve(self, config: Config) -> Resource:
        matches = [
            adapter
            for adapter in self._source_adapters
            if adapter.source_type == config.source_type
        ]
        if not matches:
            raise UnsupportedSourceError(
                f"Source type {config.source_type!r} is not supported"
            )
        if len(matches) > 1:
            raise UnsupportedSourceError(
                f"Source type {config.source_type!r} is ambiguous"
            )
        try:
            source = matches[0].load(config)
        except RhinestoneError:
            raise
        except Exception as error:
            raise ProviderMetadataError(
                f"Provider metadata for {config.source_type!r} could not be loaded"
            ) from error
        return self._resolver.resolve(source)

"""Explicit local access to downloaded GSI fundamental vector data."""

from pathlib import Path
from typing import Any, Mapping, cast

from ....errors import ConfigValidationError, ResourceNotFoundError
from ....models import Config, ResourceCandidate, Source
from .._knowledge import entry_point, source, string
from ..base import ProviderAdapter


class GsiFundamentalAdapter(ProviderAdapter):
    source_type = "gsi-fundamental"

    def __init__(self) -> None:
        super().__init__(get_json=lambda url, params: None)

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
        if settings.get("dataset") != "basic":
            raise ConfigValidationError("Initial support is for basic vector data")
        path = Path(string(settings, "path")).absolute()
        if not path.is_file():
            raise ResourceNotFoundError("Local fundamental data file does not exist")
        metadata = settings.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ConfigValidationError("metadata must be an object")
        metadata = cast(Mapping[str, Any], metadata)
        for key in (
            "mesh",
            "feature_type",
            "schema_version",
            "download_spec_version",
            "crs",
            "source_url",
        ):
            string(metadata, key)
        archive = settings.get("archive")
        if archive not in (None, "zip"):
            raise ConfigValidationError("Only ZIP archives are supported")
        member = entry_point(settings)
        if member is not None and archive != "zip":
            raise ConfigValidationError("entry_point requires archive=zip")
        candidate = ResourceCandidate(
            str(path),
            "gml",
            "application/gml+xml",
            {
                "archive": archive,
                "access_kind": "file",
                "access_options": {"entry_point": member},
                "metadata": metadata,
            },
        )
        return source(
            self.source_type,
            metadata["mesh"],
            metadata,
            (candidate,),
            capabilities=("file",),
        )

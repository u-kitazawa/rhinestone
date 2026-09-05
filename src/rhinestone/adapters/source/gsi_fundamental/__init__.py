"""Explicit local access to downloaded GSI fundamental vector data."""

from pathlib import Path
from typing import Any, Mapping, cast

from ....errors import ResourceNotFoundError
from ....models import Config, ResourceCandidate, Source
from .._knowledge import entry_point, source, string
from ..base import ProviderAdapter


class GsiFundamentalAdapter(ProviderAdapter):
    source_type = "gsi-fundamental"

    def __init__(self) -> None:
        super().__init__(get_json=lambda url, params: None)

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
        path = Path(string(settings, "path")).absolute()
        if not path.is_file():
            raise ResourceNotFoundError("Local fundamental data file does not exist")
        metadata = cast(Mapping[str, Any], settings["metadata"])
        archive = settings.get("archive")
        member = entry_point(settings)
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

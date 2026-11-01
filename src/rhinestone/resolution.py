"""Provider-side construction of unique Resources and portable AccessPlans."""

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from .errors import UnsupportedAccessError
from .models import (
    AccessPlan,
    DiscoveryRecord,
    Metadata,
    Provenance,
    Reference,
    Resource,
)
from .representations import canonical_format


def resource_from_delivery(
    *,
    reference: Reference,
    uri: str,
    format: str | None,
    media_type: str | None,
    metadata: Metadata,
    provenance: Provenance,
    kind: str | None = None,
    options: Mapping[str, Any] | None = None,
    encoding: str | None = None,
    archive: str | None = None,
    service: str | None = None,
    credential: str | None = None,
    discovery: DiscoveryRecord | None = None,
) -> Resource:
    """Build one Resource after a Provider selected one delivery target.

    This validates and normalizes a selected delivery; it performs no candidate
    selection. Providers call it once per distribution/resource.
    """
    normalized = canonical_format(format)
    if normalized is None and kind is None:
        return Resource(
            uri=uri,
            format=None,
            media_type=media_type,
            metadata=metadata,
            provenance=provenance,
            access_plan=None,
            reference=reference,
            discovery=discovery,
        )
    if kind is None:
        if normalized == "cog":
            kind = "remote-dataset"
        elif normalized in {"wms", "wfs", "api", "ogc-api-features"}:
            kind = "service-query"
        else:
            kind = "file"
    plan_options = dict(options or {})
    if encoding is not None:
        plan_options.setdefault("encoding", encoding)
    if kind == "file":
        if archive is None and normalized in {"shapefile-zip", "zip"}:
            archive = "zip"
        if archive not in (None, "zip"):
            raise UnsupportedAccessError("Only archive='zip' is supported")
        entry_point = plan_options.get("entry_point")
        if entry_point is not None:
            if archive != "zip" or not isinstance(entry_point, str):
                raise UnsupportedAccessError(
                    "entry_point requires archive='zip' and a string path"
                )
            path = PurePosixPath(entry_point)
            if (
                not entry_point.strip()
                or not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in entry_point
            ):
                raise UnsupportedAccessError(
                    "entry_point must be a safe relative archive path"
                )
        if archive is not None:
            plan_options["archive"] = archive
    plan = AccessPlan(
        kind=kind,
        uri=uri,
        format=normalized,
        media_type=media_type,
        options=plan_options,
        provider=provenance.provider,
        service=service,
        credential=credential,
    )
    return Resource(
        uri=uri,
        format=normalized,
        media_type=media_type,
        metadata=metadata,
        provenance=provenance,
        access_plan=plan,
        reference=reference,
        discovery=discovery,
    )


__all__ = ["resource_from_delivery"]

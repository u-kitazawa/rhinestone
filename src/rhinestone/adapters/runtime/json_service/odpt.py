"""Translate an ODPT AccessPlan at the credential-release boundary.

DestinationPolicy authorization is owned by JsonServiceAdapter and must run
before this preparer is called. No Provider adapter instance is needed to
execute a portable plan.
"""

from collections.abc import Mapping
from typing import Any, cast

from ....errors import ConfigValidationError
from ....models import AccessPlan
from ...ports import CredentialPort


def prepare_odpt_request(
    plan: AccessPlan,
    credentials: CredentialPort,
) -> tuple[Mapping[str, Any], Mapping[str, str]]:
    """Validate the ODPT request shape before retrieving its logical credential."""
    expected_uri = plan.options.get("endpoint")
    if (
        plan.kind != "service-query"
        or plan.service != "odpt"
        or not isinstance(expected_uri, str)
        or plan.uri != expected_uri
    ):
        raise ConfigValidationError("Credential destination is not an ODPT endpoint")
    params_value = plan.options.get("params")
    credential = plan.credential
    if not isinstance(params_value, Mapping) or not isinstance(credential, str):
        raise ConfigValidationError("ODPT service plan is incomplete")
    params: dict[str, Any] = dict(cast(Mapping[str, Any], params_value))
    params["acl:consumerKey"] = credentials.get(credential)
    return params, {}

"""Built-in standard-library HTTP transport."""

import json
from typing import Any, Mapping, Optional, cast
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from .errors import ProviderResponseError

_TIMEOUT_SECONDS = 30
_DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "rhinestone",
}


class JsonDocument(dict[str, Any]):
    """Decoded JSON object together with the URI that supplied it."""

    def __init__(self, value: Mapping[str, Any], response_uri: str) -> None:
        super().__init__(value)
        self.response_uri = response_uri


def get_json(
    url: str,
    params: Mapping[str, Any],
    headers: Optional[Mapping[str, str]] = None,
) -> Any:
    """Fetch and decode JSON over HTTP using the standard library."""
    request = _request(url, params, headers)
    opener = (
        build_opener(_NoRedirectHandler())
        if getattr(headers, "_rhinestone_no_redirects", False)
        else None
    )
    open_request = opener.open if opener is not None else urlopen
    with open_request(request, timeout=_TIMEOUT_SECONDS) as response:
        try:
            decoded = json.load(response)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProviderResponseError("Provider response is not valid JSON") from None
        if isinstance(decoded, Mapping):
            response_uri = getattr(response, "geturl", lambda: request.full_url)()
            return JsonDocument(
                cast(Mapping[str, Any], decoded), response_uri or request.full_url
            )
        return decoded


def get_text(url: str) -> str:
    """Fetch a text document without following HTTP redirects."""
    request = Request(url, headers={"User-Agent": "rhinestone"})
    opener = build_opener(_NoRedirectHandler())
    with opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset)


class JsonServiceRuntime:
    """Small requests-compatible runtime used by ``JsonServiceAdapter``."""

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: int,
        allow_redirects: bool,
    ) -> "JsonResponse":
        request = _request(url, params, headers)
        opener = build_opener(_NoRedirectHandler())
        try:
            response = opener.open(request, timeout=timeout)
        except HTTPError as error:
            response = error
        with response:
            charset = response.headers.get_content_charset() or "utf-8"
            status_code = cast(int, response.getcode())
            return JsonResponse(status_code, response.read(), charset)


class JsonResponse:
    """Subset of the requests response contract used by ``JsonServiceAdapter``."""

    def __init__(self, status_code: int, body: bytes, charset: str) -> None:
        self.status_code = status_code
        self._body = body
        self._charset = charset

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise OSError(f"HTTP request failed with status {self.status_code}")

    def json(self) -> Any:
        return json.loads(self._body.decode(self._charset))


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Optional[Request]:
        return None


def _request(
    url: str,
    params: Mapping[str, Any],
    headers: Optional[Mapping[str, str]] = None,
) -> Request:
    request_url = _append_query(url, params)
    return Request(
        request_url,
        headers={**_DEFAULT_HEADERS, **dict(headers or {})},
    )


def _append_query(url: str, params: Mapping[str, Any]) -> str:
    """Append parameters without replacing or normalizing an existing query."""
    additional_query = urlencode(params, doseq=True)
    if not additional_query:
        return url
    components = urlsplit(url)
    query = (
        f"{components.query}&{additional_query}"
        if components.query
        else additional_query
    )
    return urlunsplit(components._replace(query=query))

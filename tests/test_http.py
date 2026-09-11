import io
from email.message import Message
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from rhinestone import _http  # pyright: ignore[reportPrivateUsage]
from rhinestone.errors import ProviderResponseError


class _Headers:
    def __init__(self, charset: Optional[str]) -> None:
        self._charset = charset

    def get_content_charset(self) -> Optional[str]:
        return self._charset


class _Response:
    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        charset: Optional[str] = None,
        final_url: Optional[str] = None,
    ) -> None:
        self._body = body
        self._status = status
        self.headers = _Headers(charset)
        self._final_url = final_url

    def __enter__(self) -> "_Response":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self._status

    def geturl(self) -> str:
        return self._final_url or "https://example.test/api"


class _Opener:
    def __init__(self, result: Any) -> None:
        self._result = result
        self.calls: Dict[str, Any] = {}

    def open(self, request: Request, *, timeout: int) -> Any:
        self.calls["request"] = request
        self.calls["timeout"] = timeout
        self.calls["count"] = self.calls.get("count", 0) + 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def test_get_json_builds_query_and_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: Dict[str, Any] = {}

    def open_url(request: Request, *, timeout: int) -> _Response:
        calls["request"] = request
        calls["timeout"] = timeout
        return _Response(b'{"ok": true}')

    monkeypatch.setattr(_http, "urlopen", open_url)

    assert _http.get_json(
        "https://example.test/api",
        {"q": "a b", "tag": ["x", "y"]},
        {"X-Test": "yes"},
    ) == {"ok": True}
    request = calls["request"]
    assert isinstance(request, Request)
    assert request.full_url == "https://example.test/api?q=a+b&tag=x&tag=y"
    headers = dict(request.header_items())
    assert headers["Accept"] == "application/json"
    assert headers["User-agent"] == "rhinestone"
    assert headers["X-test"] == "yes"
    assert calls["timeout"] == 30


def test_get_json_preserves_existing_query_and_fragment_without_new_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: Dict[str, Any] = {}

    def open_url(request: Request, *, timeout: int) -> _Response:
        calls["request"] = request
        return _Response(b"[]")

    monkeypatch.setattr(_http, "urlopen", open_url)

    url = "https://example.test/api?tenant=a#section"

    assert _http.get_json(url, {}) == []
    assert calls["request"].full_url == url


def test_get_json_appends_multi_value_query_before_fragment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: Dict[str, Any] = {}

    def open_url(request: Request, *, timeout: int) -> _Response:
        calls["request"] = request
        return _Response(b"[]")

    monkeypatch.setattr(_http, "urlopen", open_url)

    assert (
        _http.get_json(
            "https://example.test/api?tenant=a&tag=original#section",
            {"q": "x", "tag": ["b", "c"]},
        )
        == []
    )
    assert calls["request"].full_url == (
        "https://example.test/api?tenant=a&tag=original&q=x&tag=b&tag=c#section"
    )


def test_get_json_preserves_final_response_uri_for_json_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def open_url(request: Request, *, timeout: int) -> _Response:
        return _Response(b'{"ok": true}', final_url="https://redirected.example/final")

    monkeypatch.setattr(_http, "urlopen", open_url)

    response = _http.get_json("https://example.test/api", {})

    assert response == {"ok": True}
    assert response.response_uri == "https://redirected.example/final"


@pytest.mark.parametrize("body", (b"{", b"<html>error</html>", b""))
def test_get_json_normalizes_invalid_json(
    monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    def open_url(request: Request, *, timeout: int) -> _Response:
        return _Response(body)

    monkeypatch.setattr(_http, "urlopen", open_url)

    with pytest.raises(ProviderResponseError, match="not valid JSON"):
        _http.get_json("https://example.test/api", {})


def test_get_json_rejects_redirects_for_marked_credential_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: Dict[str, Any] = {}

    def build_test_opener(handler: object) -> _Opener:
        calls["handler"] = handler
        return _Opener(_Response(b"{}"))

    monkeypatch.setattr(_http, "build_opener", build_test_opener)

    class CredentialHeaders(dict[str, str]):
        _rhinestone_no_redirects = True

    assert (
        _http.get_json(
            "https://example.test/api", {}, CredentialHeaders({"Authorization": "x"})
        )
        == {}
    )
    assert isinstance(  # pyright: ignore[reportPrivateUsage]
        calls["handler"],
        _http._NoRedirectHandler,  # pyright: ignore[reportPrivateUsage]
    )


def test_get_text_uses_response_charset_and_utf8_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openers = iter(
        (
            _Opener(_Response("東京".encode("shift_jis"), charset="shift_jis")),
            _Opener(_Response("大阪".encode())),
        )
    )

    def build_test_opener(_handler: object) -> _Opener:
        return next(openers)

    monkeypatch.setattr(_http, "build_opener", build_test_opener)

    assert _http.get_text("https://example.test/one") == "東京"
    assert _http.get_text("https://example.test/two") == "大阪"


def test_get_text_rejects_redirect_without_following_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = Message()
    redirect = HTTPError(
        "https://example.test/catalog",
        302,
        "redirect",
        headers,
        io.BytesIO(),
    )
    opener = _Opener(redirect)

    def build_test_opener(handler: object) -> _Opener:
        assert isinstance(  # pyright: ignore[reportPrivateUsage]
            handler,
            _http._NoRedirectHandler,  # pyright: ignore[reportPrivateUsage]
        )
        return opener

    monkeypatch.setattr(_http, "build_opener", build_test_opener)

    with pytest.raises(HTTPError):
        _http.get_text("https://example.test/catalog")

    assert opener.calls["count"] == 1
    assert opener.calls["request"].full_url == "https://example.test/catalog"


def test_json_service_runtime_wraps_successful_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = _Opener(_Response(b'{"ok": true}', charset="utf-8"))

    def build_test_opener(_handler: object) -> _Opener:
        return opener

    monkeypatch.setattr(_http, "build_opener", build_test_opener)

    response = _http.JsonServiceRuntime().get(
        "https://example.test/api?tenant=a#section",
        params={"q": "station"},
        headers={"X-Test": "yes"},
        timeout=12,
        allow_redirects=False,
    )

    assert response.status_code == 200
    response.raise_for_status()
    assert response.json() == {"ok": True}
    assert opener.calls["timeout"] == 12
    request = opener.calls["request"]
    assert request.full_url == "https://example.test/api?tenant=a&q=station#section"


def test_json_service_runtime_preserves_http_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = Message()
    headers["Content-Type"] = "application/json"
    redirect = HTTPError(
        "https://example.test/api",
        302,
        "redirect",
        headers,
        io.BytesIO(b"{}"),
    )
    opener = _Opener(redirect)

    def build_test_opener(_handler: object) -> _Opener:
        return opener

    monkeypatch.setattr(_http, "build_opener", build_test_opener)

    response = _http.JsonServiceRuntime().get(
        "https://example.test/api",
        params={},
        headers={},
        timeout=30,
        allow_redirects=False,
    )

    assert response.status_code == 302
    response.raise_for_status()
    assert response.json() == {}


def test_json_response_raises_for_http_error() -> None:
    response = _http.JsonResponse(503, b"{}", "utf-8")

    with pytest.raises(OSError, match="503"):
        response.raise_for_status()


def test_no_redirect_handler_rejects_redirect() -> None:
    handler = _http._NoRedirectHandler()  # pyright: ignore[reportPrivateUsage]
    request = Request("https://example.test")

    assert (
        handler.redirect_request(
            request, None, 302, "redirect", {}, "https://other.test"
        )
        is None
    )

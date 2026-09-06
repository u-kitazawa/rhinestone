import io
from email.message import Message
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from rhinestone import _http  # pyright: ignore[reportPrivateUsage]


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
    ) -> None:
        self._body = body
        self._status = status
        self.headers = _Headers(charset)

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


class _Opener:
    def __init__(self, result: Any) -> None:
        self._result = result
        self.calls: Dict[str, Any] = {}

    def open(self, request: Request, *, timeout: int) -> Any:
        self.calls["request"] = request
        self.calls["timeout"] = timeout
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


def test_get_json_without_query_or_extra_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: Dict[str, Any] = {}

    def open_url(request: Request, *, timeout: int) -> _Response:
        calls["request"] = request
        return _Response(b"[]")

    monkeypatch.setattr(_http, "urlopen", open_url)

    assert _http.get_json("https://example.test/api", {}) == []
    assert calls["request"].full_url == "https://example.test/api"


def test_get_text_uses_response_charset_and_utf8_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        (
            _Response("東京".encode("shift_jis"), charset="shift_jis"),
            _Response("大阪".encode()),
        )
    )

    def open_url(request: Request, *, timeout: int) -> _Response:
        return next(responses)

    monkeypatch.setattr(_http, "urlopen", open_url)

    assert _http.get_text("https://example.test/one") == "東京"
    assert _http.get_text("https://example.test/two") == "大阪"


def test_json_service_runtime_wraps_successful_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = _Opener(_Response(b'{"ok": true}', charset="utf-8"))

    def build_test_opener(_handler: object) -> _Opener:
        return opener

    monkeypatch.setattr(_http, "build_opener", build_test_opener)

    response = _http.JsonServiceRuntime().get(
        "https://example.test/api",
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
    assert request.full_url == "https://example.test/api?q=station"


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

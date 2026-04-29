# -*- coding: utf-8 -*-
"""urllib3-compatible mocking utilities for testing InfluxDB client."""

import json
from contextlib import contextmanager
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs, urlencode

GET = "GET"
POST = "POST"
DELETE = "DELETE"
PUT = "PUT"


class _CaseInsensitiveDict(dict):
    """A dict subclass that allows case-insensitive key access."""

    def __init__(self, data=None):
        super().__init__()
        if data:
            for k, v in (data.items() if hasattr(data, "items") else data):
                self[k] = v

    def __setitem__(self, key, value):
        super().__setitem__(key.lower(), value)

    def __getitem__(self, key):
        return super().__getitem__(key.lower())

    def __contains__(self, key):
        return super().__contains__(key.lower())

    def get(self, key, default=None):
        return super().get(key.lower(), default)


class _MockRequest:
    """Represents a captured HTTP request."""

    def __init__(self, method, url, body, headers):
        self.method = method
        self.url = url
        self.body = body
        raw_headers = headers or {}
        self.headers = _CaseInsensitiveDict(raw_headers)
        parsed = urlparse(url)
        self.qs = parse_qs(parsed.query)

    def json(self):
        """Parse body as JSON."""
        if self.body is None:
            return None
        if isinstance(self.body, bytes):
            return json.loads(self.body.decode("utf-8"))
        return json.loads(self.body)


class _MockHTTPResponse:
    """Mimics urllib3.response.BaseHTTPResponse for testing."""

    def __init__(self, status=200, data=b"", headers=None):
        self.status = status
        self.data = data
        self.headers = headers or {}
        self._msgpack = None


class _MockerContext:
    """Tracks registered URIs and captured requests."""

    def __init__(self):
        self._registered = []
        self.requests = []

    def register_uri(self, method, url, status_code=200, text=None, content=None,
                     headers=None, request_headers=None):
        """Register a URI pattern with a mock response."""
        data = b""
        if content is not None:
            data = content
        elif text is not None:
            data = text.encode("utf-8")
        self._registered.append({
            "method": method.upper(),
            "url": url,
            "status_code": status_code,
            "data": data,
            "headers": headers or {},
            "request_headers": request_headers,
        })

    @property
    def last_request(self):
        """Return the most recently captured request."""
        return self.requests[-1] if self.requests else None

    @property
    def call_count(self):
        """Return the number of requests captured."""
        return len(self.requests)

    @property
    def request_history(self):
        """Return all captured requests (alias for requests list)."""
        return self.requests

    def _handle_request(self, method, url, fields=None, body=None, headers=None, **kwargs):
        """Side-effect function that captures requests and returns mock responses."""
        full_url = url
        if fields:
            sep = "&" if "?" in url else "?"
            full_url = url + sep + urlencode(fields)

        req = _MockRequest(method, full_url, body, headers)
        self.requests.append(req)

        for reg in reversed(self._registered):
            parsed_reg = urlparse(reg["url"])
            parsed_req = urlparse(full_url)
            if reg["method"] != method.upper():
                continue
            if parsed_reg.path != parsed_req.path:
                continue
            if reg["request_headers"] and headers:
                if not all(headers.get(k) == v for k, v in reg["request_headers"].items()):
                    continue
            return _MockHTTPResponse(
                status=reg["status_code"],
                data=reg["data"],
                headers=reg["headers"],
            )

        return _MockHTTPResponse(status=200)


class Mocker:
    """Context manager that intercepts urllib3.PoolManager.request calls.

    Usage::

        with Mocker() as m:
            m.register_uri(POST, "http://host/write", status_code=204)
            client.write_points(...)
            assert m.last_request.body == b"..."
    """

    def __enter__(self):
        self._ctx = _MockerContext()
        self._patcher = patch(
            "urllib3.PoolManager.request",
            side_effect=self._ctx._handle_request,
        )
        self._patcher.start()
        return self._ctx

    def __exit__(self, *args):
        self._patcher.stop()


@contextmanager
def _mocked_session(influxdb_client, method, status_code, body=None):
    """Context manager that patches a specific client's session.request.

    Args:
        influxdb_client: The InfluxDBClient instance to patch.
        method: Expected HTTP method (unused, kept for API compatibility).
        status_code: HTTP status code to return.
        body: Optional response body string.
    """
    data = b""
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body

    response = _MockHTTPResponse(status=status_code, data=data)

    with patch.object(influxdb_client._session, "request", return_value=response):
        yield

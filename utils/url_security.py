# -*- coding: utf-8 -*-
"""Restrict outbound HTTP(S) access for OGC / DGGS client code."""

from __future__ import annotations

import ssl
from typing import Optional

import requests
from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})
DEFAULT_TIMEOUT = 30


class UrlSecurityError(ValueError):
    """Raised when a URL is missing, malformed, or uses a disallowed scheme."""


class _HttpResponseReader:
    """Minimal file-like wrapper so callers can use ``response.read()``."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> "_HttpResponseReader":
        return self

    def __exit__(self, *args) -> None:
        pass


def validate_http_url(url: str) -> str:
    """Return *url* if it uses http or https and has a host."""
    url = (url or "").strip()
    if not url:
        raise UrlSecurityError("URL is empty")
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UrlSecurityError(
            f"URL scheme {parsed.scheme!r} is not allowed; use http or https."
        )
    if not parsed.netloc:
        raise UrlSecurityError("URL must include a host")
    return url


def is_http_url(url: str) -> bool:
    try:
        validate_http_url(url)
        return True
    except UrlSecurityError:
        return False


def _requests_verify(context: Optional[ssl.SSLContext]) -> bool:
    if context is None:
        return True
    return context.verify_mode != ssl.CERT_NONE


def safe_urlopen(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    context: Optional[ssl.SSLContext] = None,
) -> _HttpResponseReader:
    """Fetch *url* via HTTP(S) after scheme validation (http/https only)."""
    safe_url = validate_http_url(url)
    response = requests.get(
        safe_url,
        timeout=timeout,
        verify=_requests_verify(context),
    )
    response.raise_for_status()
    return _HttpResponseReader(response.content)


def safe_urlretrieve(
    url: str,
    filename: str,
    timeout: float = DEFAULT_TIMEOUT,
    context: Optional[ssl.SSLContext] = None,
) -> None:
    """Download *url* to *filename* after scheme validation."""
    with safe_urlopen(url, timeout=timeout, context=context) as response:
        data = response.read()
    with open(filename, "wb") as out:
        out.write(data)

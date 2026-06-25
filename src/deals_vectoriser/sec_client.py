"""Thin HTTP client for SEC hosts: required User-Agent, client-side rate limit, retry."""

import threading
import time

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import SEC_MAX_RPS, SEC_USER_AGENT


class _Transient(Exception):
    """Wraps retryable SEC responses (429/503) so tenacity retries them."""


class SecClient:
    """Single shared httpx client. SEC 403s any request lacking a descriptive UA."""

    def __init__(self) -> None:
        self._client = httpx.Client(
            headers={
                "User-Agent": SEC_USER_AGENT,
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        self._min_interval = 1.0 / SEC_MAX_RPS if SEC_MAX_RPS > 0 else 0.0
        self._last = 0.0
        self._lock = threading.Lock()

    def _throttle(self) -> None:
        with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    @retry(
        stop=stop_after_attempt(7),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception_type((_Transient, httpx.TransportError)),
        reraise=True,
    )
    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        self._throttle()
        r = self._client.get(url, params=params)
        # SEC hosts (esp. efts) emit sporadic 5xx that succeed on retry.
        if r.status_code == 429 or r.status_code >= 500:
            raise _Transient(f"{r.status_code} from {r.request.url}")
        r.raise_for_status()
        return r

    def get_json(self, url: str, params: dict | None = None) -> dict:
        return self._get(url, params).json()

    def get_text(self, url: str, params: dict | None = None) -> str:
        return self._get(url, params).text

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SecClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

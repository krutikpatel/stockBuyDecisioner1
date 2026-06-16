from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests
from requests import Response

from codex_backed.data.providers.base import ProviderError

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10.0
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF = 1.0
_DEFAULT_RATE_LIMIT_BACKOFF = 60.0

_KEY_PATTERN = re.compile(r"([Aa]pi[_-]?[Kk]ey|apikey|token)=([^&\s]+)", re.IGNORECASE)


def _redact(text: str) -> str:
    return _KEY_PATTERN.sub(lambda m: f"{m.group(1)}=***", text)


class HttpClient:
    """Thin wrapper around requests.get with retries, timeout, and key redaction.

    5xx and 429 (rate limit) responses are retried up to max_retries times.
    429 sleeps rate_limit_backoff_seconds before each retry.
    All other 4xx responses fail immediately (non-retryable).
    The API key is redacted from all log output and exception messages.
    """

    def __init__(
        self,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        backoff_seconds: float = _DEFAULT_BACKOFF,
        rate_limit_backoff_seconds: float = _DEFAULT_RATE_LIMIT_BACKOFF,
        session: requests.Session | None = None,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._rate_limit_backoff = rate_limit_backoff_seconds
        self._session = session or requests.Session()

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET url, parse JSON response, retry on 5xx up to max_retries.

        Raises ProviderError on 4xx, exhausted retries, or network failures.
        """
        safe_url = _redact(url)
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                time.sleep(self._backoff * attempt)
                logger.warning("Retry %d/%d for %s", attempt, self._max_retries, safe_url)
            try:
                resp: Response = self._session.get(url, params=params, timeout=self._timeout)
            except requests.Timeout as exc:
                raise ProviderError(f"Request timed out after {self._timeout}s: {safe_url}") from exc
            except requests.RequestException as exc:
                raise ProviderError(f"Network error: {_redact(str(exc))}") from exc

            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise ProviderError(f"Invalid JSON from {safe_url}: {exc}") from exc

            if resp.status_code == 429:
                logger.warning(
                    "HTTP 429 rate limit from %s (attempt %d/%d) — sleeping %.0fs",
                    safe_url, attempt + 1, self._max_retries + 1, self._rate_limit_backoff,
                )
                time.sleep(self._rate_limit_backoff)
                last_exc = ProviderError(
                    f"HTTP 429 rate limited from {safe_url} (attempt {attempt + 1}/{self._max_retries + 1})"
                )
                continue

            if 400 <= resp.status_code < 500:
                raise ProviderError(
                    f"HTTP {resp.status_code} (non-retryable) from {safe_url}: {_redact(resp.text[:200])}"
                )

            last_exc = ProviderError(
                f"HTTP {resp.status_code} from {safe_url} (attempt {attempt + 1}/{self._max_retries + 1})"
            )
            logger.warning(str(last_exc))

        assert last_exc is not None
        raise ProviderError(
            f"Max retries ({self._max_retries}) exhausted for {safe_url}"
        ) from last_exc

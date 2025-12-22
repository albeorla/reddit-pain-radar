"""Centralized HTTP client configuration for Reddit scraping.

Provides a properly configured httpx.AsyncClient with:
- Connection limits to avoid overwhelming servers
- Appropriate timeouts
- Browser-like headers
- Context manager for resource cleanup
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC

import httpx

from .logging_config import get_logger

logger = get_logger(__name__)

# Default configuration
DEFAULT_TIMEOUT = httpx.Timeout(
    timeout=30.0,  # Total timeout
    connect=10.0,  # Connection timeout
    read=20.0,  # Read timeout
    write=10.0,  # Write timeout
)

DEFAULT_LIMITS = httpx.Limits(
    max_connections=20,
    max_keepalive_connections=10,
    keepalive_expiry=30.0,
)

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "DNT": "1",
}

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@asynccontextmanager
async def create_http_client(
    user_agent: str | None = None,
    timeout: httpx.Timeout | None = None,
    limits: httpx.Limits | None = None,
    extra_headers: dict | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    """Create a configured HTTP client for Reddit scraping.

    Args:
        user_agent: Custom user agent (uses default if not provided)
        timeout: Custom timeout config (uses DEFAULT_TIMEOUT if not provided)
        limits: Custom connection limits (uses DEFAULT_LIMITS if not provided)
        extra_headers: Additional headers to include

    Yields:
        Configured httpx.AsyncClient

    Example:
        async with create_http_client() as client:
            response = await client.get("https://www.reddit.com/r/test/hot.rss")
    """
    headers = DEFAULT_HEADERS.copy()
    headers["User-Agent"] = user_agent or DEFAULT_USER_AGENT

    if extra_headers:
        headers.update(extra_headers)

    client = httpx.AsyncClient(
        timeout=timeout or DEFAULT_TIMEOUT,
        limits=limits or DEFAULT_LIMITS,
        headers=headers,
        follow_redirects=True,
        http2=False,  # Requires 'h2' package, disabled for simplicity
    )

    logger.debug("http_client_created", user_agent=headers["User-Agent"][:50])

    try:
        yield client
    finally:
        await client.aclose()
        logger.debug("http_client_closed")


def parse_retry_after(response: httpx.Response) -> float | None:
    """Parse Retry-After header from response.

    Args:
        response: HTTP response

    Returns:
        Seconds to wait, or None if header not present/parseable
    """
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return None

    try:
        # Try parsing as integer (seconds)
        return float(retry_after)
    except ValueError:
        pass

    try:
        # Try parsing as HTTP-date (e.g., "Wed, 21 Oct 2015 07:28:00 GMT")
        from datetime import datetime
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(retry_after)
        now = datetime.now(UTC)
        delta = (dt - now).total_seconds()
        return max(0.0, delta)
    except (ValueError, TypeError):
        pass

    return None

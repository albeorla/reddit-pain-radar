"""Retry policies for HTTP requests and LLM calls.

Provides reusable retry decorators with:
- Proper exception handling for httpx and OpenAI
- Logging of retry attempts
- Exponential backoff with jitter
"""

from __future__ import annotations

import asyncio

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .logging_config import get_logger

logger = get_logger(__name__)


# Transient HTTP exceptions that should trigger retries
HTTP_TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.PoolTimeout,
    httpx.NetworkError,
)


class TransientHTTPError(Exception):
    """Wrapper for transient HTTP errors (429, 5xx) that should be retried."""

    def __init__(self, message: str, status_code: int, retry_after: float | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class RateLimitError(TransientHTTPError):
    """Rate limit (429) error with optional Retry-After."""

    pass


def log_retry_attempt(retry_state: RetryCallState) -> None:
    """Log retry attempts with context."""
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    wait_time = retry_state.next_action.sleep if retry_state.next_action else 0

    logger.warning(
        "retry_attempt",
        attempt=retry_state.attempt_number,
        wait_seconds=round(wait_time, 2),
        exception_type=type(exception).__name__ if exception else None,
        exception_msg=str(exception)[:100] if exception else None,
    )


# Retry policy for HTTP requests (RSS, JSON scraping)
http_retry = retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
    retry=retry_if_exception_type(HTTP_TRANSIENT_EXCEPTIONS + (TransientHTTPError,)),
    before_sleep=log_retry_attempt,
)


# Retry policy for LLM calls (more attempts, longer backoff for rate limits)
llm_retry = retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=2, max=60, jitter=5),
    retry=retry_if_exception_type(
        (
            TimeoutError,
            ConnectionError,
            # OpenAI/LangChain exceptions are handled by the library,
            # but we catch common transient issues
        )
    ),
    before_sleep=log_retry_attempt,
)


def check_response_for_retry(response: httpx.Response) -> None:
    """Check response status and raise appropriate exception for retry.

    Args:
        response: HTTP response to check

    Raises:
        RateLimitError: For 429 responses
        TransientHTTPError: For 5xx responses
        httpx.HTTPStatusError: For other 4xx errors (not retried)
    """
    if response.status_code == 429:
        from .http_client import parse_retry_after

        retry_after = parse_retry_after(response)
        raise RateLimitError(
            "Rate limited (429)",
            status_code=429,
            retry_after=retry_after,
        )

    if response.status_code >= 500:
        raise TransientHTTPError(
            f"Server error ({response.status_code})",
            status_code=response.status_code,
        )

    # For other errors, raise normally (won't retry)
    response.raise_for_status()


async def adaptive_sleep(retry_after: float | None, default: float = 1.0) -> None:
    """Sleep for the appropriate amount of time.

    Args:
        retry_after: Seconds from Retry-After header (if present)
        default: Default sleep time if no Retry-After
    """
    sleep_time = retry_after if retry_after is not None else default
    # Cap at 60 seconds to avoid extremely long waits
    sleep_time = min(sleep_time, 60.0)

    if sleep_time > 0:
        logger.debug("sleeping", seconds=round(sleep_time, 2))
        await asyncio.sleep(sleep_time)

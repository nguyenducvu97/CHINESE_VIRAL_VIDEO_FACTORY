"""Token Bucket Rate Limiter and Retry Utilities for Video Discovery."""

import time
import random
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter to protect external sources from hammering."""

    def __init__(self, rate: float = 1.0, capacity: float = 5.0):
        """
        Args:
            rate: Tokens added per second. (e.g. 1.0 = 1 request per second)
            capacity: Maximum burst capacity of tokens.
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()

    def acquire(self, tokens: float = 1.0, timeout: Optional[float] = 10.0) -> bool:
        """Wait until enough tokens are available or timeout expires."""
        start_time = time.monotonic()
        while True:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            if timeout is not None:
                spent = now - start_time
                if spent >= timeout:
                    return False
                remaining = timeout - spent
                needed = tokens - self.tokens
                sleep_time = min(needed / self.rate, remaining, 0.2)
                if sleep_time <= 0:
                    return False
                time.sleep(sleep_time)
            else:
                needed = tokens - self.tokens
                sleep_time = min(needed / self.rate, 0.2)
                time.sleep(sleep_time)


def execute_with_retry(
    func: Callable[[], Any],
    max_retries: int = 3,
    initial_backoff: float = 1.0,
    backoff_factor: float = 2.0,
    max_backoff: float = 10.0,
    retryable_exceptions: tuple = (Exception,)
) -> Any:
    """Execute callable with exponential backoff and randomized jitter."""
    attempt = 0
    backoff = initial_backoff

    while True:
        try:
            return func()
        except retryable_exceptions as exc:
            attempt += 1
            if attempt > max_retries:
                logger.error(f"Function {func} failed after {max_retries} retries: {exc}")
                raise exc

            jitter = random.uniform(0.1, 0.5) * backoff
            sleep_time = min(backoff + jitter, max_backoff)
            logger.warning(
                f"Attempt {attempt}/{max_retries} failed: {exc}. Retrying in {sleep_time:.2f}s..."
            )
            time.sleep(sleep_time)
            backoff = min(backoff * backoff_factor, max_backoff)

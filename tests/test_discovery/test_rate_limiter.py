"""Unit tests for TokenBucketRateLimiter and Retry Utilities."""

import pytest
from src.discovery.rate_limiter import TokenBucketRateLimiter, execute_with_retry


def test_token_bucket_acquire_and_deplete():
    """Test rate limiter acquires tokens up to burst capacity and honors limits."""
    limiter = TokenBucketRateLimiter(rate=2.0, capacity=2.0)
    
    # Burst capacity allows 2 immediate acquisitions
    assert limiter.acquire(1.0, timeout=0.1) is True
    assert limiter.acquire(1.0, timeout=0.1) is True

    # Immediate third acquisition should timeout if timeout is very small
    assert limiter.acquire(1.0, timeout=0.05) is False


def test_execute_with_retry_success():
    """Test retry utility succeeds when callable eventually succeeds."""
    attempts = 0

    def flaky_func():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ValueError("Temporary failure")
        return "SUCCESS"

    result = execute_with_retry(flaky_func, max_retries=3, initial_backoff=0.01)
    assert result == "SUCCESS"
    assert attempts == 2


def test_execute_with_retry_exceeds_max():
    """Test retry utility raises exception when max retries exceeded."""
    def always_failing():
        raise RuntimeError("Persistent network error")

    with pytest.raises(RuntimeError):
        execute_with_retry(always_failing, max_retries=2, initial_backoff=0.01)

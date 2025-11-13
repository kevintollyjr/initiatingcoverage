"""Rate limiting utilities"""
import time
from typing import Optional
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter to respect API/site limits"""

    def __init__(self, calls_per_second: float = 10.0):
        """
        Args:
            calls_per_second: Maximum number of calls allowed per second
        """
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0

    def wait(self):
        """Wait if necessary to respect rate limit"""
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        self.last_call = time.time()

    def __call__(self, func):
        """Decorator to rate-limit a function"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.wait()
            return func(*args, **kwargs)
        return wrapper


class BackoffRateLimiter:
    """Rate limiter with exponential backoff on errors"""

    def __init__(
        self,
        calls_per_second: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ):
        self.rate_limiter = RateLimiter(calls_per_second)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def __call__(self, func):
        """Decorator with rate limiting and retry logic"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(self.max_retries):
                try:
                    self.rate_limiter.wait()
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        raise
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
            return None
        return wrapper

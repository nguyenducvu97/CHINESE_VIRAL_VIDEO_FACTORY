"""Abstract Base Class for Video Discovery Adapters."""

from abc import ABC, abstractmethod
import logging
from typing import List, Optional

from src.core.models import StandardVideoItem
from src.discovery.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


class BaseDiscoveryAdapter(ABC):
    """Abstract class defining the contract for source adapters."""

    def __init__(
        self,
        platform_name: str,
        rate_limit: float = 1.0,
        burst_capacity: float = 3.0,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
    ):
        self.platform_name = platform_name
        self.rate_limiter = TokenBucketRateLimiter(rate=rate_limit, capacity=burst_capacity)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @abstractmethod
    def fetch_trending(
        self, page: int = 1, page_size: int = 20, dry_run: bool = False
    ) -> List[StandardVideoItem]:
        """Fetch trending or hot viral videos from the source.
        
        Args:
            page: Pagination index (1-based).
            page_size: Maximum items requested per page.
            dry_run: When True, returns pre-verified fixture data without live network calls.
        """
        pass

    @abstractmethod
    def fetch_by_id(
        self, item_id: str, dry_run: bool = False
    ) -> Optional[StandardVideoItem]:
        """Fetch detailed metadata for a specific video ID.
        
        Args:
            item_id: Source item identifier.
            dry_run: When True, returns pre-verified fixture item without live network calls.
        """
        pass

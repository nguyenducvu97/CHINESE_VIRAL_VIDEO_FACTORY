"""Discovery Service coordinating adapters, deduplication, and persistence."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.core.models import StandardVideoItem
from src.discovery.base_adapter import BaseDiscoveryAdapter
from src.discovery.dedup import DeduplicationStore

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryRunResult:
    """Audit summary for a discovery execution run."""
    run_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    platform: str = "all"
    total_fetched: int = 0
    new_unique_added: int = 0
    duplicates_filtered: int = 0
    errors: List[str] = field(default_factory=list)
    items: List[StandardVideoItem] = field(default_factory=list)


class DiscoveryService:
    """High-level service managing video discovery across multiple adapters."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.store = DeduplicationStore(storage_path=storage_path)
        self.adapters: Dict[str, BaseDiscoveryAdapter] = {}

    def register_adapter(self, adapter: BaseDiscoveryAdapter) -> None:
        """Register a new source adapter."""
        self.adapters[adapter.platform_name] = adapter
        logger.info(f"Registered discovery adapter: {adapter.platform_name}")

    def discover_trending(
        self,
        platform_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        dry_run: bool = False,
    ) -> DiscoveryRunResult:
        """Run video discovery across registered adapters with automatic deduplication.
        
        Args:
            platform_name: Specific platform to query, or None for all registered adapters.
            page: 1-indexed pagination.
            page_size: Maximum videos per page per adapter.
            dry_run: When True, uses verified fixtures without external API calls.
        """
        result = DiscoveryRunResult(platform=platform_name or "all")
        targets = (
            {platform_name: self.adapters[platform_name]}
            if platform_name and platform_name in self.adapters
            else self.adapters
        )

        all_fetched: List[StandardVideoItem] = []

        for name, adapter in targets.items():
            try:
                items = adapter.fetch_trending(page=page, page_size=page_size, dry_run=dry_run)
                all_fetched.extend(items)
                logger.info(f"Adapter '{name}' returned {len(items)} items")
            except Exception as e:
                err_msg = f"Adapter '{name}' failed: {e}"
                logger.error(err_msg)
                result.errors.append(err_msg)

        result.total_fetched = len(all_fetched)

        # Deduplicate against existing store
        unique, duplicates = self.store.filter_duplicates(all_fetched)
        result.new_unique_added = len(unique)
        result.duplicates_filtered = len(duplicates)
        result.items = unique

        logger.info(
            f"Discovery complete. Fetched: {result.total_fetched}, "
            f"New Unique: {result.new_unique_added}, "
            f"Duplicates: {result.duplicates_filtered}"
        )
        return result

    def get_by_dedup_key(self, dedup_key: str) -> Optional[StandardVideoItem]:
        """Retrieve stored video by canonical dedup key."""
        return self.store.get(dedup_key)

    def list_all_stored(self) -> List[StandardVideoItem]:
        """List all unique videos currently in the store."""
        return self.store.get_all()

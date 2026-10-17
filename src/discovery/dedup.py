"""Deduplication and Canonical Store for Discovered Videos."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from src.core.models import StandardVideoItem

logger = logging.getLogger(__name__)


def generate_dedup_key(source_platform: str, source_item_id: str) -> str:
    """Generate a canonical, stable deduplication key."""
    clean_platform = source_platform.strip().lower()
    clean_id = source_item_id.strip()
    return f"{clean_platform}:{clean_id}"


class DeduplicationStore:
    """Persistent and in-memory store ensuring idempotency and zero duplicate records."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path
        self._items: Dict[str, StandardVideoItem] = {}
        self._seen_keys: Set[str] = set()

        if self.storage_path and self.storage_path.exists():
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load stored items from disk."""
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for raw in data:
                    item = StandardVideoItem(**raw)
                    self._items[item.dedup_key] = item
                    self._seen_keys.add(item.dedup_key)
            logger.info(f"Loaded {len(self._items)} existing items from {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to load items from {self.storage_path}: {e}")

    def _persist(self) -> None:
        """Persist items to disk if storage path configured."""
        if not self.storage_path:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                data = [item.model_dump() for item in self._items.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist deduplication store to {self.storage_path}: {e}")

    def is_duplicate(self, dedup_key: str) -> bool:
        """Check if dedup key has already been seen."""
        return dedup_key in self._seen_keys

    def add(self, item: StandardVideoItem) -> bool:
        """Add an item if not duplicate.
        Returns:
            True if newly added, False if duplicate.
        """
        if self.is_duplicate(item.dedup_key):
            return False

        self._items[item.dedup_key] = item
        self._seen_keys.add(item.dedup_key)
        self._persist()
        return True

    def filter_duplicates(
        self, items: List[StandardVideoItem]
    ) -> Tuple[List[StandardVideoItem], List[StandardVideoItem]]:
        """Filter list of items into unique vs duplicate items.
        
        Returns:
            Tuple of (unique_items, duplicate_items)
        """
        unique: List[StandardVideoItem] = []
        duplicates: List[StandardVideoItem] = []

        for item in items:
            if self.is_duplicate(item.dedup_key):
                duplicates.append(item)
            else:
                self._items[item.dedup_key] = item
                self._seen_keys.add(item.dedup_key)
                unique.append(item)

        if unique:
            self._persist()

        return unique, duplicates

    def get(self, dedup_key: str) -> Optional[StandardVideoItem]:
        """Retrieve stored item by dedup key."""
        return self._items.get(dedup_key)

    def get_all(self) -> List[StandardVideoItem]:
        """Return all stored items."""
        return list(self._items.values())

    def count(self) -> int:
        """Return total unique items stored."""
        return len(self._items)

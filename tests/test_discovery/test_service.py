"""Unit tests for DiscoveryService orchestration."""

import pytest
from pathlib import Path
from src.discovery.adapters.bilibili_adapter import BilibiliDiscoveryAdapter
from src.discovery.service import DiscoveryService


def test_discovery_service_dry_run_idempotency(tmp_path: Path):
    """Test full discovery flow and verify idempotency on subsequent runs."""
    store_file = tmp_path / "service_store.json"
    service = DiscoveryService(storage_path=store_file)
    bilibili_adapter = BilibiliDiscoveryAdapter()
    service.register_adapter(bilibili_adapter)

    # First Run: should fetch fixtures and store unique items
    res1 = service.discover_trending(platform_name="bilibili", page=1, page_size=10, dry_run=True)
    assert res1.total_fetched == 3
    assert res1.new_unique_added == 3
    assert res1.duplicates_filtered == 0
    assert len(res1.errors) == 0

    # Second Run: identical input must produce 0 new items and 3 filtered duplicates
    res2 = service.discover_trending(platform_name="bilibili", page=1, page_size=10, dry_run=True)
    assert res2.total_fetched == 3
    assert res2.new_unique_added == 0
    assert res2.duplicates_filtered == 3
    assert len(res2.errors) == 0

    # Verification: retrieved items from store match
    stored = service.list_all_stored()
    assert len(stored) == 3

    item = service.get_by_dedup_key("bilibili:BV1KiJk67EQ9")
    assert item is not None
    assert item.title == "我造了一块会飞的滑板，直接飞跃山谷！"

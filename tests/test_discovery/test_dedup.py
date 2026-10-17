"""Unit tests for DeduplicationStore and Idempotency."""

import pytest
from pathlib import Path
from src.core.models import AuthorInfo, InteractionMetrics, StandardVideoItem
from src.discovery.dedup import DeduplicationStore, generate_dedup_key


def _make_dummy_item(platform: str, item_id: str, title: str = "Title") -> StandardVideoItem:
    dedup_key = generate_dedup_key(platform, item_id)
    return StandardVideoItem(
        dedup_key=dedup_key,
        source_platform=platform,
        source_item_id=item_id,
        canonical_url=f"https://example.com/{platform}/{item_id}",
        title=title,
        author=AuthorInfo(id="author_1", name="Creator 1"),
        metrics=InteractionMetrics(views=1000, likes=100),
    )


def test_dedup_key_generation():
    """Verify canonical key formatting and whitespace/case normalization."""
    assert generate_dedup_key("BILIBILI", " BV123 ") == "bilibili:BV123"
    assert generate_dedup_key("douyin", "7890123") == "douyin:7890123"


def test_in_memory_deduplication():
    """Verify duplicate rejection in memory."""
    store = DeduplicationStore()
    item1 = _make_dummy_item("bilibili", "BV1")
    item2 = _make_dummy_item("bilibili", "BV1")  # duplicate
    item3 = _make_dummy_item("bilibili", "BV2")  # unique

    assert store.add(item1) is True
    assert store.add(item2) is False  # rejected as duplicate
    assert store.add(item3) is True
    assert store.count() == 2


def test_filter_duplicates_batch():
    """Verify batch filtering into unique and duplicate sets."""
    store = DeduplicationStore()
    items = [
        _make_dummy_item("bilibili", "BV1"),
        _make_dummy_item("bilibili", "BV2"),
        _make_dummy_item("bilibili", "BV1"),  # duplicate
        _make_dummy_item("douyin", "1001"),
    ]

    unique, duplicates = store.filter_duplicates(items)
    assert len(unique) == 3
    assert len(duplicates) == 1
    assert duplicates[0].dedup_key == "bilibili:BV1"

    # Running filter again with same items should result in all duplicates
    unique_again, duplicates_again = store.filter_duplicates(items)
    assert len(unique_again) == 0
    assert len(duplicates_again) == 4


def test_store_disk_persistence(tmp_path: Path):
    """Verify store saves to disk and restores accurately."""
    store_file = tmp_path / "dedup_store.json"
    store1 = DeduplicationStore(storage_path=store_file)
    store1.add(_make_dummy_item("bilibili", "BV_PERSIST_1", "Saved Title"))
    store1.add(_make_dummy_item("bilibili", "BV_PERSIST_2", "Second Title"))
    assert store1.count() == 2

    # Instantiate new store pointing to same file
    store2 = DeduplicationStore(storage_path=store_file)
    assert store2.count() == 2
    assert store2.is_duplicate("bilibili:BV_PERSIST_1") is True
    loaded_item = store2.get("bilibili:BV_PERSIST_1")
    assert loaded_item is not None
    assert loaded_item.title == "Saved Title"

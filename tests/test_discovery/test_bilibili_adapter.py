"""Unit tests for BilibiliDiscoveryAdapter."""

import pytest
from unittest.mock import MagicMock
import httpx

from src.core.exceptions import DiscoveryError, SourceBlockedError
from src.core.models import StandardVideoItem
from src.discovery.adapters.bilibili_adapter import BilibiliDiscoveryAdapter


def test_bilibili_dry_run_trending():
    """Verify dry-run mode returns valid schema items without network."""
    adapter = BilibiliDiscoveryAdapter()
    items = adapter.fetch_trending(page=1, page_size=2, dry_run=True)
    assert len(items) == 2
    for item in items:
        assert isinstance(item, StandardVideoItem)
        assert item.source_platform == "bilibili"
        assert item.dedup_key.startswith("bilibili:")
        assert item.metrics.views > 0
        assert item.metrics.likes > 0
        assert item.author.name != ""
        assert len(item.missing_fields) > 0


def test_bilibili_dry_run_pagination():
    """Verify pagination slices fixtures properly."""
    adapter = BilibiliDiscoveryAdapter()
    page1 = adapter.fetch_trending(page=1, page_size=2, dry_run=True)
    page2 = adapter.fetch_trending(page=2, page_size=2, dry_run=True)

    assert len(page1) == 2
    assert len(page2) == 1
    assert page1[0].dedup_key != page2[0].dedup_key


def test_bilibili_dry_run_fetch_by_id():
    """Verify fetch_by_id in dry-run mode."""
    adapter = BilibiliDiscoveryAdapter()
    item = adapter.fetch_by_id("BV1KiJk67EQ9", dry_run=True)
    assert item is not None
    assert item.title == "我造了一块会飞的滑板，直接飞跃山谷！"

    non_existent = adapter.fetch_by_id("BV_NON_EXISTENT", dry_run=True)
    assert non_existent is None


def test_bilibili_mock_code_352_risk_control(monkeypatch):
    """Verify that Bilibili -352 code properly triggers SourceBlockedError."""
    adapter = BilibiliDiscoveryAdapter()

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": -352, "message": "-352", "ttl": 1}
    mock_client.get.return_value = mock_resp

    monkeypatch.setattr(adapter, "_get_client", lambda: mock_client)

    with pytest.raises(SourceBlockedError) as exc_info:
        adapter.fetch_trending(page=1, page_size=10, dry_run=False)

    assert "-352" in str(exc_info.value)


def test_bilibili_mock_server_error(monkeypatch):
    """Verify that HTTP 500 error raises DiscoveryError."""
    adapter = BilibiliDiscoveryAdapter()

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client.get.return_value = mock_resp

    monkeypatch.setattr(adapter, "_get_client", lambda: mock_client)

    with pytest.raises(DiscoveryError):
        adapter.fetch_trending(page=1, page_size=10, dry_run=False)

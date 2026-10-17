"""Live Integration Test against public Bilibili endpoint.
Proves that BilibiliDiscoveryAdapter interacts with the real external source without mocking.
"""

import pytest
from src.core.exceptions import SourceBlockedError
from src.core.models import StandardVideoItem
from src.discovery.adapters.bilibili_adapter import BilibiliDiscoveryAdapter


@pytest.mark.integration
def test_bilibili_live_discovery():
    """Verify live discovery against real public Bilibili ranking API.
    Either returns real items (HTTP 200 code 0) or correctly classifies real anti-bot challenge (-352).
    """
    adapter = BilibiliDiscoveryAdapter(rate_limit=0.5, burst_capacity=1.0, timeout_seconds=15.0)

    try:
        items = adapter.fetch_trending(page=1, page_size=5, dry_run=False)
        assert len(items) > 0, "Expected at least 1 real item from live ranking API"

        sample = items[0]
        assert isinstance(sample, StandardVideoItem)
        assert sample.source_platform == "bilibili"
        assert sample.dedup_key.startswith("bilibili:BV")
        assert len(sample.title) > 0
        assert sample.canonical_url.startswith("https://www.bilibili.com/video/BV")
        assert sample.author.name is not None
        assert sample.metrics.views is not None and sample.metrics.views > 0
        assert sample.metrics.likes is not None
        assert sample.metrics.has_sufficient_metrics is True

        safe_title = sample.title.encode("ascii", "replace").decode("ascii")
        print(f"\n[LIVE TEST VERIFIED] Successfully fetched real Chinese viral video: {safe_title} ({sample.dedup_key}) with {sample.metrics.views} views!")
    except SourceBlockedError as e:
        print(f"\n[LIVE TEST VERIFIED] Real Bilibili anti-bot challenge (-352) accurately captured without crash: {e}")
        assert "-352" in str(e)
    finally:
        adapter.close()

"""Bilibili Public Discovery Adapter for Trending Chinese Videos."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import httpx

from src.core.exceptions import (
    DiscoveryError,
    InvalidResponseError,
    SourceBlockedError,
)
from src.core.models import (
    AuthorInfo,
    InteractionMetrics,
    RightsStatus,
    StandardVideoItem,
)
from src.discovery.base_adapter import BaseDiscoveryAdapter
from src.discovery.rate_limiter import execute_with_retry

logger = logging.getLogger(__name__)

# Sample offline fixture for dry-run testing and offline fallback
BILIBILI_FIXTURES: List[Dict[str, Any]] = [
    {
        "bvid": "BV1KiJk67EQ9",
        "aid": 1139485123,
        "title": "我造了一块会飞的滑板，直接飞跃山谷！",
        "desc": "耗时3个月，自主研发涵道风扇飞行滑板，终于试飞成功！",
        "tname": "极客DIY",
        "pic": "https://i0.hdslb.com/bfs/archive/sample1.jpg",
        "duration": 482,
        "pubdate": 1740000000,
        "owner": {
            "mid": 9821345,
            "name": "神奇阿宇Ayu",
            "face": "https://i0.hdslb.com/bfs/face/sample_face1.jpg",
        },
        "stat": {
            "view": 4526574,
            "like": 227289,
            "reply": 9845,
            "share": 31867,
            "favorite": 105432,
        },
    },
    {
        "bvid": "BV1ab421M7xy",
        "aid": 1139485999,
        "title": "当程序员穿越回古代当御医，用代码治病？",
        "desc": "爆笑短剧：把脉如同debug，针灸就像打补丁！",
        "tname": "搞笑",
        "pic": "https://i0.hdslb.com/bfs/archive/sample2.jpg",
        "duration": 185,
        "pubdate": 1740086400,
        "owner": {
            "mid": 6543210,
            "name": "极客喜剧社",
            "face": "https://i0.hdslb.com/bfs/face/sample_face2.jpg",
        },
        "stat": {
            "view": 1892000,
            "like": 142000,
            "reply": 3400,
            "share": 15600,
            "favorite": 52000,
        },
    },
    {
        "bvid": "BV1xy411c7zz",
        "aid": 1139486111,
        "title": "中国非遗打铁花，夜空下千度铁水如漫天流星！",
        "desc": "实拍河南确山打铁花，千年传承的东方浪漫与硬核视觉盛宴。",
        "tname": "人文历史",
        "pic": "https://i0.hdslb.com/bfs/archive/sample3.jpg",
        "duration": 320,
        "pubdate": 1740172800,
        "owner": {
            "mid": 7788990,
            "name": "寻味东方纪实",
            "face": "https://i0.hdslb.com/bfs/face/sample_face3.jpg",
        },
        "stat": {
            "view": 3105000,
            "like": 312000,
            "reply": 8200,
            "share": 48900,
            "favorite": 189000,
        },
    },
]


class BilibiliDiscoveryAdapter(BaseDiscoveryAdapter):
    """Adapter for discovering trending videos from Bilibili's public ranking endpoints."""

    RANKING_API_URL = "https://api.bilibili.com/x/web-interface/ranking/v2"
    VIEW_API_URL = "https://api.bilibili.com/x/web-interface/view"

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    def __init__(
        self,
        rate_limit: float = 1.0,
        burst_capacity: float = 3.0,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
    ):
        super().__init__(
            platform_name="bilibili",
            rate_limit=rate_limit,
            burst_capacity=burst_capacity,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Create or return HTTP client initialized with standard session cookies."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                headers=self.DEFAULT_HEADERS,
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
            # Warm up session with initial homepage ping to establish standard session cookies
            try:
                self._client.get("https://www.bilibili.com/")
            except Exception as e:
                logger.debug(f"Bilibili session warmup notice: {e}")
        return self._client

    def close(self) -> None:
        """Close underlying HTTP client."""
        if self._client and not self._client.is_closed:
            self._client.close()

    def _convert_raw_item(self, raw: Dict[str, Any]) -> StandardVideoItem:
        """Convert Bilibili raw API item into StandardVideoItem contract."""
        bvid = raw.get("bvid", "")
        if not bvid:
            raise InvalidResponseError("Raw item missing 'bvid' field")

        owner = raw.get("owner", {}) or {}
        stat = raw.get("stat", {}) or {}

        # Track missing fields explicitly
        missing_fields: List[str] = []
        if not raw.get("desc"):
            missing_fields.append("description")
        if not owner.get("face"):
            missing_fields.append("author_avatar")
        if "direct_video_stream_url" not in raw:
            missing_fields.append("direct_video_stream_url")
        if "author_verified" not in owner:
            missing_fields.append("author_verified")

        # Parse publication date
        pubdate = raw.get("pubdate")
        published_at_str = None
        if pubdate:
            try:
                published_at_str = datetime.fromtimestamp(pubdate, tz=timezone.utc).isoformat()
            except Exception:
                published_at_str = None

        author = AuthorInfo(
            id=str(owner.get("mid", "")),
            name=owner.get("name", "Unknown Creator"),
            url=f"https://space.bilibili.com/{owner.get('mid')}" if owner.get("mid") else None,
            avatar_url=owner.get("face"),
            is_verified=False,
        )

        metrics = InteractionMetrics(
            views=stat.get("view"),
            likes=stat.get("like"),
            comments=stat.get("reply"),
            shares=stat.get("share"),
            favorites=stat.get("favorite"),
        )

        canonical_url = f"https://www.bilibili.com/video/{bvid}"

        return StandardVideoItem(
            dedup_key=f"bilibili:{bvid}",
            source_platform="bilibili",
            source_item_id=bvid,
            canonical_url=canonical_url,
            title=raw.get("title", ""),
            description=raw.get("desc"),
            category_hint=raw.get("tname"),
            media_urls={
                "cover_url": raw.get("pic"),
                "video_url": None,  # Raw stream requires PlayURL endpoint
            },
            duration_seconds=float(raw.get("duration", 0)) if raw.get("duration") else None,
            published_at=published_at_str,
            author=author,
            metrics=metrics,
            rights_status=RightsStatus.PENDING_VERIFICATION,
            missing_fields=missing_fields,
            raw_metadata=raw,
        )

    def fetch_trending(
        self, page: int = 1, page_size: int = 20, dry_run: bool = False
    ) -> List[StandardVideoItem]:
        """Fetch trending Chinese videos from Bilibili."""
        if dry_run:
            logger.info("Executing Bilibili fetch_trending in DRY-RUN mode.")
            start = (page - 1) * page_size
            end = start + page_size
            fixtures = BILIBILI_FIXTURES[start:end]
            return [self._convert_raw_item(raw) for raw in fixtures]

        # Acquire rate-limit token
        if not self.rate_limiter.acquire(timeout=10.0):
            raise DiscoveryError("Rate limit token acquisition timed out")

        def _request_api() -> List[Dict[str, Any]]:
            client = self._get_client()
            resp = client.get(self.RANKING_API_URL)
            if resp.status_code != 200:
                raise DiscoveryError(f"Bilibili API returned HTTP {resp.status_code}")

            data = resp.json()
            code = data.get("code")
            if code == -352:
                raise SourceBlockedError(
                    "Bilibili risk control challenge (-352). Anti-bot safeguard encountered."
                )
            if code != 0:
                raise DiscoveryError(f"Bilibili API returned error code {code}: {data.get('message')}")

            items = data.get("data", {}).get("list", [])
            return items

        try:
            raw_items = execute_with_retry(
                _request_api,
                max_retries=self.max_retries,
                retryable_exceptions=(httpx.RequestError, httpx.TimeoutException),
            )
        except Exception as e:
            logger.error(f"Failed to fetch Bilibili trending videos: {e}")
            raise

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        sliced = raw_items[start_idx:end_idx]

        results: List[StandardVideoItem] = []
        for raw in sliced:
            try:
                item = self._convert_raw_item(raw)
                results.append(item)
            except Exception as e:
                logger.warning(f"Skipping malformed Bilibili item: {e}")

        return results

    def fetch_by_id(
        self, item_id: str, dry_run: bool = False
    ) -> Optional[StandardVideoItem]:
        """Fetch video metadata for a specific Bilibili bvid."""
        clean_bvid = item_id.strip()
        if dry_run:
            for fix in BILIBILI_FIXTURES:
                if fix["bvid"] == clean_bvid:
                    return self._convert_raw_item(fix)
            return None

        if not self.rate_limiter.acquire(timeout=10.0):
            raise DiscoveryError("Rate limit token acquisition timed out")

        def _request_view() -> Dict[str, Any]:
            client = self._get_client()
            resp = client.get(self.VIEW_API_URL, params={"bvid": clean_bvid})
            if resp.status_code == 404:
                return {}
            if resp.status_code != 200:
                raise DiscoveryError(f"Bilibili View API returned HTTP {resp.status_code}")
            data = resp.json()
            code = data.get("code")
            if code == -352:
                raise SourceBlockedError("Bilibili risk control challenge (-352)")
            if code == -404:
                return {}
            if code != 0:
                raise DiscoveryError(f"Bilibili View API returned error code {code}: {data.get('message')}")
            return data.get("data", {})

        raw_data = execute_with_retry(
            _request_view,
            max_retries=self.max_retries,
            retryable_exceptions=(httpx.RequestError, httpx.TimeoutException),
        )

        if not raw_data:
            return None

        return self._convert_raw_item(raw_data)

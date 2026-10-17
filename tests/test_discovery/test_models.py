"""Unit tests for Core Data Models and Schema Validation."""

import pytest
from pydantic import ValidationError

from src.core.models import (
    AuthorInfo,
    InteractionMetrics,
    ProcessingStatus,
    RightsStatus,
    StandardVideoItem,
)


def test_standard_video_item_valid():
    """Test valid video item construction and field validation."""
    author = AuthorInfo(
        id="author_101",
        name="测试创作者",
        url="https://example.com/user/101",
        avatar_url="https://example.com/avatar.jpg",
        is_verified=True,
    )
    metrics = InteractionMetrics(
        views=150000,
        likes=12000,
        comments=450,
        shares=1800,
        favorites=3200,
    )

    item = StandardVideoItem(
        dedup_key="bilibili:BV1TestItem123",
        source_platform="bilibili",
        source_item_id="BV1TestItem123",
        canonical_url="https://www.bilibili.com/video/BV1TestItem123",
        title="测试中文爆款视频标题",
        description="这是一个详细的测试视频描述内容",
        category_hint="搞笑",
        author=author,
        metrics=metrics,
        missing_fields=["direct_video_stream_url"],
    )

    assert item.dedup_key == "bilibili:BV1TestItem123"
    assert item.title == "测试中文爆款视频标题"
    assert item.metrics.has_sufficient_metrics is True
    assert item.rights_status == RightsStatus.PENDING_VERIFICATION
    assert item.processing_status == ProcessingStatus.DISCOVERED
    assert "direct_video_stream_url" in item.missing_fields


def test_dedup_key_invalid_format():
    """Test dedup_key validation requires ':' separator."""
    author = AuthorInfo(id="1", name="Creator")
    metrics = InteractionMetrics(views=100)

    with pytest.raises(ValidationError):
        StandardVideoItem(
            dedup_key="invalid_dedup_key_without_colon",
            source_platform="bilibili",
            source_item_id="123",
            canonical_url="https://example.com",
            title="Title",
            author=author,
            metrics=metrics,
        )


def test_missing_fields_tracking():
    """Test missing fields tracking when metrics or description are not provided."""
    author = AuthorInfo(id="2", name="Unknown")
    metrics = InteractionMetrics(views=None, likes=None)

    item = StandardVideoItem(
        dedup_key="douyin:742890001",
        source_platform="douyin",
        source_item_id="742890001",
        canonical_url="https://example.com/v/1",
        title="无描述视频",
        author=author,
        metrics=metrics,
        missing_fields=["description", "views", "likes", "author_avatar"],
    )

    assert item.metrics.has_sufficient_metrics is False
    assert len(item.missing_fields) == 4
    assert "description" in item.missing_fields

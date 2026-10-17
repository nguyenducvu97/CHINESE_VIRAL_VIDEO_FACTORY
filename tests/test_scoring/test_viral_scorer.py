"""Unit tests for ViralScorer."""

import pytest
from src.core.models import AuthorInfo, InteractionMetrics, StandardVideoItem
from src.scoring.models import ConfidenceLevel, ReviewStatus, VideoCategory
from src.scoring.viral_scorer import ViralScorer


def _make_item(
    views=None,
    likes=None,
    shares=None,
    comments=None,
    title="测试搞笑短剧视频",
    category_hint="搞笑",
) -> StandardVideoItem:
    return StandardVideoItem(
        dedup_key="bilibili:BV_TEST_SCORE",
        source_platform="bilibili",
        source_item_id="BV_TEST_SCORE",
        canonical_url="https://www.bilibili.com/video/BV_TEST_SCORE",
        title=title,
        category_hint=category_hint,
        author=AuthorInfo(id="author_1", name="Creator 1"),
        metrics=InteractionMetrics(
            views=views,
            likes=likes,
            shares=shares,
            comments=comments,
        ),
    )


def test_score_viral_high_potential():
    """Verify high engagement video receives high score and ELIGIBLE_FOR_REVIEW."""
    scorer = ViralScorer()
    # 4.5M views, 227k likes (~5.0%), 31k shares (~0.7%), 9.8k comments (~0.22%)
    item = _make_item(views=4526574, likes=227289, shares=31867, comments=9845)
    scored = scorer.score_video(item)

    assert scored.measured_viral_score is not None
    assert scored.measured_viral_score >= 70.0
    assert scored.status == ReviewStatus.ELIGIBLE_FOR_REVIEW
    assert scored.confidence_level == ConfidenceLevel.HIGH
    assert len(scored.scoring_explanation) >= 4
    # Ensure explanations contain concrete metrics
    joined_exp = " ".join(scored.scoring_explanation)
    assert "4,526,574" in joined_exp
    assert "ĐỦ ĐIỀU KIỆN DUYỆT" in joined_exp


def test_score_insufficient_data():
    """Verify missing views or likes returns INSUFFICIENT_DATA without fabricating."""
    scorer = ViralScorer()
    item = _make_item(views=None, likes=None)
    scored = scorer.score_video(item)

    assert scored.measured_viral_score is None
    assert scored.inferred_potential_score is None
    assert scored.confidence_level == ConfidenceLevel.INSUFFICIENT_DATA
    assert scored.status == ReviewStatus.INSUFFICIENT_DATA
    assert any("INSUFFICIENT_DATA" in exp for exp in scored.scoring_explanation)


def test_score_zero_or_negative_views():
    """Verify zero views does not cause division by zero."""
    scorer = ViralScorer()
    item = _make_item(views=0, likes=0)
    scored = scorer.score_video(item)

    assert scored.confidence_level == ConfidenceLevel.INSUFFICIENT_DATA
    assert scored.measured_viral_score is None


def test_score_low_views():
    """Verify views under minimum threshold receives LOW_POTENTIAL."""
    scorer = ViralScorer()
    item = _make_item(views=500, likes=20, shares=2, comments=1)
    scored = scorer.score_video(item)

    assert scored.status == ReviewStatus.LOW_POTENTIAL
    assert scored.confidence_level == ConfidenceLevel.LOW
    assert scored.measured_viral_score < 50.0


def test_score_reproducibility():
    """Verify that multiple evaluations of identical input yield the exact same score."""
    scorer = ViralScorer()
    item = _make_item(views=2000000, likes=120000, shares=15000, comments=4000)

    score1 = scorer.score_video(item)
    score2 = scorer.score_video(item)

    assert score1.measured_viral_score == score2.measured_viral_score
    assert score1.inferred_potential_score == score2.inferred_potential_score
    assert score1.status == score2.status
    assert score1.category == score2.category

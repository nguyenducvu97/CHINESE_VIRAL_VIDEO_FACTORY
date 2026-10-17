"""Unit tests for TaxonomyClassifier."""

import pytest
from src.scoring.models import VideoCategory
from src.scoring.taxonomy import TaxonomyClassifier


@pytest.fixture
def classifier():
    return TaxonomyClassifier()


def test_classify_ai_movie(classifier):
    res = classifier.classify(title="Sora生成的科幻微电影：未来纪元", description="全流程AI生成视频与概念短片")
    assert res.category == VideoCategory.AI_MOVIE
    assert res.confidence >= 0.5
    assert "sora" in [k.lower() for k in res.matched_keywords]


def test_classify_comedy(classifier):
    res = classifier.classify(title="当程序员穿越回古代，爆笑短剧沙雕名场面！")
    assert res.category == VideoCategory.COMEDY
    assert res.confidence >= 0.5
    assert "爆笑" in res.matched_keywords or "短剧" in res.matched_keywords


def test_classify_knowledge_diy(classifier):
    res = classifier.classify(
        title="我造了一块会飞的滑板，极客手工大制作",
        category_hint="极客DIY",
    )
    assert res.category == VideoCategory.KNOWLEDGE
    assert res.confidence >= 0.6


def test_classify_other_fallback(classifier):
    res = classifier.classify(title="Lorem ipsum dolor sit amet 1234567")
    assert res.category == VideoCategory.OTHER
    assert res.confidence == 0.3
    assert len(res.matched_keywords) == 0

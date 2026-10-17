"""Viral Potential Scoring Engine for CVVF."""

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from src.core.models import StandardVideoItem
from src.scoring.models import (
    ClassificationResult,
    ConfidenceLevel,
    ReviewStatus,
    ScoredVideoItem,
    VideoCategory,
)
from src.scoring.taxonomy import TaxonomyClassifier

logger = logging.getLogger(__name__)

DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "scoring_rules.yaml"


class ViralScorer:
    """Calculates transparent, reproducible viral scores based on measured facts vs inference."""

    def __init__(
        self,
        rules_path: Optional[Path] = None,
        taxonomy_classifier: Optional[TaxonomyClassifier] = None,
    ):
        self.rules_path = rules_path or DEFAULT_RULES_PATH
        self.classifier = taxonomy_classifier or TaxonomyClassifier()
        self.config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load scoring rules from YAML configuration."""
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Scoring config not found at: {self.rules_path}")

        with open(self.rules_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        logger.info(f"Loaded viral scoring config v{self.config.get('version', 'unknown')}")

    def score_video(self, item: StandardVideoItem) -> ScoredVideoItem:
        """Evaluate and score a StandardVideoItem.
        
        Strictly enforces:
        1. No fabrication of views or engagement metrics.
        2. Assigns INSUFFICIENT_DATA if metrics are missing.
        3. Generates transparent, human-readable explanations.
        """
        # Step 1: Classify content category
        classification: ClassificationResult = self.classifier.classify(
            title=item.title,
            description=item.description,
            tags=item.tags,
            category_hint=item.category_hint,
        )

        metrics = item.metrics
        explanations: List[str] = []

        # Check for insufficient data
        if not metrics or metrics.views is None or metrics.views <= 0 or metrics.likes is None:
            explanations.append("Thiếu số liệu lượt xem hoặc lượt thích thực tế từ nguồn.")
            explanations.append("Hệ thống từ chối tự suy diễn số liệu và gán trạng thái INSUFFICIENT_DATA.")

            return ScoredVideoItem(
                item_id=item.id,
                dedup_key=item.dedup_key,
                canonical_url=item.canonical_url,
                title=item.title,
                taxonomy_version=classification.taxonomy_version,
                category=classification.category,
                category_confidence=classification.confidence,
                measured_viral_score=None,
                inferred_potential_score=None,
                confidence_level=ConfidenceLevel.INSUFFICIENT_DATA,
                status=ReviewStatus.INSUFFICIENT_DATA,
                scoring_explanation=explanations,
            )

        weights = self.config.get("weights", {})
        benchmarks = self.config.get("benchmarks", {})
        thresholds = self.config.get("thresholds", {})

        views = metrics.views
        likes = metrics.likes
        shares = metrics.shares
        comments = metrics.comments

        min_views = thresholds.get("min_views_required", 1000)
        if views < min_views:
            explanations.append(
                f"Lượt xem thực đo ({views:,}) chưa đạt ngưỡng tối thiểu ({min_views:,}) để đánh giá độ lan truyền."
            )
            return ScoredVideoItem(
                item_id=item.id,
                dedup_key=item.dedup_key,
                canonical_url=item.canonical_url,
                title=item.title,
                taxonomy_version=classification.taxonomy_version,
                category=classification.category,
                category_confidence=classification.confidence,
                measured_viral_score=round(float(views) / min_views * 20.0, 1),
                inferred_potential_score=20.0,
                confidence_level=ConfidenceLevel.LOW,
                status=ReviewStatus.LOW_POTENTIAL,
                scoring_explanation=explanations,
            )

        # 1. Volume Score (logarithmic scale up to max_view_baseline)
        max_views = benchmarks.get("max_view_baseline", 10000000)
        log_view = math.log10(views)
        log_max = math.log10(max_views)
        volume_score = min(max((log_view / log_max) * 100.0, 0.0), 100.0)
        explanations.append(f"Quy mô người xem: {views:,} lượt xem (Đạt {volume_score:.1f}/100 điểm quy mô)")

        # 2. Like Rate Score (likes / views vs baseline 4%)
        like_baseline = benchmarks.get("like_rate_baseline", 0.04)
        like_rate = likes / views
        like_score = min(max((like_rate / like_baseline) * 50.0, 0.0), 100.0)
        explanations.append(
            f"Tỷ lệ thích (Like/View): {like_rate * 100:.2f}% (Chuẩn ngành: {like_baseline * 100:.1f}%, đạt {like_score:.1f}/100 điểm)"
        )

        # 3. Share Rate Score (shares / views vs baseline 0.5%)
        share_baseline = benchmarks.get("share_rate_baseline", 0.005)
        if shares is not None:
            share_rate = shares / views
            share_score = min(max((share_rate / share_baseline) * 50.0, 0.0), 100.0)
            explanations.append(
                f"Tỷ lệ chia sẻ (Share/View): {share_rate * 100:.2f}% (Chuẩn lan truyền: {share_baseline * 100:.1f}%, đạt {share_score:.1f}/100 điểm)"
            )
        else:
            share_score = like_score * 0.8
            explanations.append("Nguồn không cung cấp lượt chia sẻ thực tế; tạm nội suy thận trọng từ tỷ lệ thích.")

        # 4. Comment Rate Score (comments / views vs baseline 0.2%)
        comment_baseline = benchmarks.get("comment_rate_baseline", 0.002)
        if comments is not None:
            comment_rate = comments / views
            comment_score = min(max((comment_rate / comment_baseline) * 50.0, 0.0), 100.0)
            explanations.append(
                f"Tỷ lệ thảo luận (Comment/View): {comment_rate * 100:.2f}% (Chuẩn tương tác: {comment_baseline * 100:.1f}%, đạt {comment_score:.1f}/100 điểm)"
            )
        else:
            comment_score = 50.0
            explanations.append("Nguồn không cung cấp lượt bình luận; sử dụng mức cơ sở 50 điểm.")

        # Calculate final measured viral score
        w_vol = weights.get("view_volume", 0.25)
        w_like = weights.get("like_rate", 0.35)
        w_share = weights.get("share_rate", 0.25)
        w_comment = weights.get("comment_rate", 0.15)

        measured_score = (
            w_vol * volume_score
            + w_like * like_score
            + w_share * share_score
            + w_comment * comment_score
        )
        measured_score = round(min(max(measured_score, 0.0), 100.0), 1)

        # Category Inferred Potential Adjustment (+2 to +5 points for highly viral formats)
        cat_bonus = 0.0
        if classification.category in [VideoCategory.COMEDY, VideoCategory.SHORT_FILM, VideoCategory.AI_MOVIE]:
            cat_bonus = 4.0
            explanations.append(f"Chuyên mục '{classification.category.value}' có xu hướng viral cao trên video ngắn (+4 điểm tiềm năng).")
        elif classification.category == VideoCategory.KNOWLEDGE:
            cat_bonus = 2.0
            explanations.append("Chuyên mục 'knowledge' có thời gian lưu giữ người xem tốt (+2 điểm tiềm năng).")

        inferred_score = round(min(measured_score + cat_bonus, 100.0), 1)

        # Review eligibility status
        review_thresh = thresholds.get("eligible_for_review", 65.0)
        if measured_score >= review_thresh:
            status = ReviewStatus.ELIGIBLE_FOR_REVIEW
            explanations.append(f"ĐỦ ĐIỀU KIỆN DUYỆT (Điểm {measured_score} >= ngưỡng {review_thresh}).")
        else:
            status = ReviewStatus.LOW_POTENTIAL
            explanations.append(f"TIỀM NĂNG THẤP (Điểm {measured_score} < ngưỡng {review_thresh}).")

        # Confidence level
        confidence = (
            ConfidenceLevel.HIGH
            if shares is not None and comments is not None
            else ConfidenceLevel.MEDIUM
        )

        return ScoredVideoItem(
            item_id=item.id,
            dedup_key=item.dedup_key,
            canonical_url=item.canonical_url,
            title=item.title,
            taxonomy_version=classification.taxonomy_version,
            category=classification.category,
            category_confidence=classification.confidence,
            measured_viral_score=measured_score,
            inferred_potential_score=inferred_score,
            confidence_level=confidence,
            status=status,
            scoring_explanation=explanations,
        )

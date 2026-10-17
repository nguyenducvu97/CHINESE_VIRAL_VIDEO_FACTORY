"""Scoring and Classification Data Contracts for CVVF."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class VideoCategory(str, Enum):
    """Phân loại nhóm nội dung theo Taxonomy v1.0.0."""
    AI_MOVIE = "ai_movie"
    SHORT_FILM = "short_film"
    DRAMA_SERIES = "drama_series"
    COMEDY = "comedy"
    DAILY_LIFE = "daily_life"
    KNOWLEDGE = "knowledge"
    ANIMATION = "animation"
    OTHER = "other"


class ConfidenceLevel(str, Enum):
    """Mức độ tin cậy của điểm số phân tích."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ReviewStatus(str, Enum):
    """Trạng thái đánh giá video cho quy trình duyệt."""
    ELIGIBLE_FOR_REVIEW = "ELIGIBLE_FOR_REVIEW"
    LOW_POTENTIAL = "LOW_POTENTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ClassificationResult(BaseModel):
    """Kết quả phân loại chuyên mục."""
    taxonomy_version: str = "1.0.0"
    category: VideoCategory
    confidence: float = Field(..., ge=0.0, le=1.0)
    matched_keywords: List[str] = Field(default_factory=list)


class ScoredVideoItem(BaseModel):
    """Bản ghi video đã được phân loại và chấm điểm viral."""
    item_id: str = Field(..., description="ID tham chiếu đến StandardVideoItem")
    dedup_key: str = Field(..., description="Khóa định danh chống trùng canonical")
    canonical_url: str = Field(..., description="URL gốc của video")
    title: str = Field(..., description="Tiêu đề gốc tiếng Trung")
    taxonomy_version: str = "1.0.0"
    category: VideoCategory = Field(..., description="Nhóm phân loại")
    category_confidence: float = Field(..., ge=0.0, le=1.0)
    measured_viral_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Điểm viral tính toán từ số liệu thực tế"
    )
    inferred_potential_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Điểm tiềm năng suy luận kết hợp chuyên mục"
    )
    confidence_level: ConfidenceLevel = Field(..., description="Độ tin cậy của số liệu")
    status: ReviewStatus = Field(..., description="Trạng thái đề xuất duyệt")
    scoring_explanation: List[str] = Field(
        default_factory=list, description="Giải thích căn cứ chấm điểm minh bạch"
    )
    calculated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Thời điểm chấm điểm (ISO-8601 UTC)"
    )

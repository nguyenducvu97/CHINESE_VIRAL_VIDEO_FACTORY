"""Core Data Models and Contracts for CHINESE_VIRAL_VIDEO_FACTORY (CVVF)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator


class RightsStatus(str, Enum):
    """Trạng thái bản quyền và quyền sử dụng video."""
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    PUBLIC_ACCESSIBLE = "PUBLIC_ACCESSIBLE"
    CREATIVE_COMMONS = "CREATIVE_COMMONS"
    RESTRICTED_COPYRIGHT = "RESTRICTED_COPYRIGHT"
    APPROVED_BY_USER = "APPROVED_BY_USER"
    REJECTED = "REJECTED"


class ProcessingStatus(str, Enum):
    """Trạng thái vòng đời xử lý video trong hệ thống."""
    DISCOVERED = "DISCOVERED"
    FILTERED_OUT = "FILTERED_OUT"
    READY_FOR_SCORING = "READY_FOR_SCORING"
    SCORED = "SCORED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    SUBTITLED = "SUBTITLED"
    DUBBED = "DUBBED"
    RENDERED = "RENDERED"
    APPROVED_FOR_PUBLISH = "APPROVED_FOR_PUBLISH"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class AuthorInfo(BaseModel):
    """Thông tin tác giả / kênh nguồn."""
    id: str = Field(..., description="ID định danh tác giả trên nền tảng nguồn")
    name: str = Field(..., description="Tên hiển thị của tác giả")
    url: Optional[str] = Field(None, description="URL trang cá nhân tác giả")
    avatar_url: Optional[str] = Field(None, description="Ảnh đại diện tác giả")
    is_verified: bool = Field(False, description="Tài khoản đã xác minh hay chưa")


class InteractionMetrics(BaseModel):
    """Số liệu tương tác thực đo từ nguồn.
    Nghiêm cấm bịa đặt số liệu nếu nguồn không cung cấp.
    """
    views: Optional[int] = Field(None, description="Lượt xem thực đo")
    likes: Optional[int] = Field(None, description="Lượt thích thực đo")
    comments: Optional[int] = Field(None, description="Lượt bình luận thực đo")
    shares: Optional[int] = Field(None, description="Lượt chia sẻ thực đo")
    favorites: Optional[int] = Field(None, description="Lượt lưu yêu thích thực đo")
    collected_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Thời điểm thu thập số liệu (ISO-8601 UTC)"
    )

    @property
    def has_sufficient_metrics(self) -> bool:
        """Kiểm tra có đủ số liệu thực tế để chấm điểm viral hay không."""
        return self.views is not None and self.views > 0 and self.likes is not None


class StandardVideoItem(BaseModel):
    """Cấu trúc dữ liệu chuẩn hóa cho video thu thập từ mọi nguồn."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="ID nội bộ duy nhất")
    dedup_key: str = Field(..., description="Khóa định danh chống trùng (vd: bilibili:BV1xxx)")
    source_platform: str = Field(..., description="Tên nền tảng (bilibili, douyin, kuaishou, etc.)")
    source_item_id: str = Field(..., description="ID gốc trên nền tảng")
    canonical_url: str = Field(..., description="URL gốc có thể truy cập")
    title: str = Field(..., description="Tiêu đề gốc tiếng Trung")
    description: Optional[str] = Field(None, description="Mô tả nội dung gốc")
    tags: List[str] = Field(default_factory=list, description="Danh sách nhãn / hashtag")
    category_hint: Optional[str] = Field(None, description="Gợi ý chuyên mục từ nền tảng gốc")
    media_urls: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Đường dẫn media (video_url, cover_url, audio_url)"
    )
    duration_seconds: Optional[float] = Field(None, description="Thời lượng video (giây)")
    published_at: Optional[str] = Field(None, description="Thời điểm đăng video gốc (ISO-8601)")
    author: AuthorInfo = Field(..., description="Thông tin tác giả")
    metrics: InteractionMetrics = Field(..., description="Số liệu tương tác thực đo")
    rights_status: RightsStatus = Field(
        default=RightsStatus.PENDING_VERIFICATION,
        description="Trạng thái quyền sử dụng"
    )
    processing_status: ProcessingStatus = Field(
        default=ProcessingStatus.DISCOVERED,
        description="Trạng thái quy trình xử lý"
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="Danh sách các trường nguồn không cung cấp"
    )
    discovery_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Thời điểm hệ thống phát hiện (ISO-8601 UTC)"
    )
    raw_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dữ liệu thô gốc từ API/Adapter phục vụ kiểm toán"
    )

    @field_validator("dedup_key")
    @classmethod
    def validate_dedup_key(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError("dedup_key must follow the pattern '<platform>:<item_id>'")
        return v

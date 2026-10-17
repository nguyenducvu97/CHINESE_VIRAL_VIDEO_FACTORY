"""Data contracts for Video Rendering and Quality Control."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class VideoVariantType(str, Enum):
    ORIGINAL_PRESERVED = "ORIGINAL_PRESERVED"
    VIETSUB = "VIETSUB"
    DUBBED_VIETSUB = "DUBBED_VIETSUB"


class VideoQCInspection(BaseModel):
    """Chi tiết kết quả kiểm định chất lượng video sau khi render."""
    is_valid: bool = Field(..., description="True nếu vượt qua tất cả kiểm định QC")
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    aspect_ratio: str = Field(..., description="Tỷ lệ khung hình (vd: 16:9 hoặc 9:16)")
    video_codec: str = Field(..., description="Codec video (vd: h264, hevc)")
    audio_codec: Optional[str] = Field(None, description="Codec âm thanh (vd: aac, mp3)")
    duration_seconds: float = Field(..., ge=0.0)
    file_size_bytes: int = Field(..., ge=0)
    is_playable: bool = Field(..., description="Kiểm tra giải mã video thành công không bị giật/đơ")
    checksum_sha256: str = Field(..., description="Mã băm toàn vẹn SHA-256")
    issues: List[str] = Field(default_factory=list)


class RenderTaskResult(BaseModel):
    """Kết quả hoàn thiện của một tác vụ render video."""
    item_id: str
    dedup_key: str
    variant_type: VideoVariantType
    output_video_path: str
    checksum_sha256: str
    qc_inspection: VideoQCInspection
    render_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

"""Data Contracts for Vietnamese Dubbing and Audio QC."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class VoiceGender(str, Enum):
    FEMALE = "FEMALE"
    MALE = "MALE"


class VoiceProfile(BaseModel):
    """Thông tin cấu hình giọng đọc TTS."""
    voice_id: str = Field(..., description="Mã định danh giọng đọc (vd: vi-VN-HoaiMyNeural)")
    gender: VoiceGender = Field(..., description="Giới tính giọng đọc")
    language: str = Field(default="vi-VN", description="Mã ngôn ngữ")
    display_name: str = Field(..., description="Tên hiển thị thân thiện")
    provider: str = Field(default="edge-tts", description="Nhà cung cấp TTS")


class DubbedSegment(BaseModel):
    """Phân đoạn âm thanh lồng tiếng đã được căn chỉnh thời lượng."""
    index: int = Field(..., ge=1)
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    target_duration_ms: int = Field(..., ge=0)
    actual_duration_ms: int = Field(..., ge=0)
    tempo_factor: float = Field(default=1.0, ge=0.5, le=2.0)
    text_vi: str
    audio_path: str


class AudioQCReport(BaseModel):
    """Báo cáo kiểm định chất lượng âm thanh sau khi mix."""
    is_passed: bool = Field(..., description="True nếu đạt chuẩn QC")
    total_duration_ms: int = Field(..., ge=0)
    drift_ms: int = Field(default=0, description="Độ lệch thời lượng so với video gốc (ms)")
    is_silent: bool = Field(default=False, description="Cảnh báo audio bị rỗng hoặc im lặng")
    is_clipping: bool = Field(default=False, description="Cảnh báo âm thanh bị vỡ tiếng (clipping)")
    warnings: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list, description="Minh bạch hạn chế kỹ thuật")


class DubbingResult(BaseModel):
    """Kết quả hoàn thiện của tác vụ lồng tiếng."""
    item_id: str
    dedup_key: str
    mixed_audio_path: str
    voice_profile: VoiceProfile
    segments: List[DubbedSegment] = Field(default_factory=list)
    qc_report: AudioQCReport
    cost: float = Field(default=0.0, description="Chi phí phát sinh thực tế (USD)")

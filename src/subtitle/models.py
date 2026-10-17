"""Subtitle and Transcription Data Contracts for CVVF."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class TranscriptSegment(BaseModel):
    """Phân đoạn nhận dạng lời thoại tiếng Trung kèm timestamp."""
    index: int = Field(..., ge=1, description="Thứ tự phân đoạn (1-based)")
    start_ms: int = Field(..., ge=0, description="Thời điểm bắt đầu (milliseconds)")
    end_ms: int = Field(..., ge=0, description="Thời điểm kết thúc (milliseconds)")
    text_zh: str = Field(..., description="Lời thoại gốc tiếng Trung")
    speaker: Optional[str] = Field(None, description="Nhãn người nói nếu nhận diện được")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Độ tin cậy của ASR")

    @model_validator(mode="after")
    def validate_timestamps(self):
        if self.end_ms <= self.start_ms:
            raise ValueError(f"end_ms ({self.end_ms}) must be strictly greater than start_ms ({self.start_ms})")
        return self


class SubtitleSegment(BaseModel):
    """Phân đoạn phụ đề hoàn chỉnh song ngữ (Trung - Việt)."""
    index: int = Field(..., ge=1, description="Thứ tự phân đoạn (1-based)")
    start_ms: int = Field(..., ge=0, description="Thời điểm bắt đầu (milliseconds)")
    end_ms: int = Field(..., ge=0, description="Thời điểm kết thúc (milliseconds)")
    text_zh: str = Field(..., description="Lời thoại gốc tiếng Trung")
    text_vi: str = Field(..., description="Bản dịch tiếng Việt tự nhiên")
    speaker: Optional[str] = Field(None, description="Nhãn người nói")

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class ValidationIssue(BaseModel):
    """Ghi nhận lỗi hoặc cảnh báo khi kiểm định phụ đề."""
    level: str = Field(..., description="'ERROR' hoặc 'WARNING'")
    segment_index: int = Field(..., description="Chỉ số phân đoạn gặp vấn đề")
    issue_code: str = Field(..., description="Mã lỗi phân loại")
    message: str = Field(..., description="Mô tả chi tiết nguyên nhân")


class SubtitleValidationReport(BaseModel):
    """Báo cáo kiểm định chất lượng phụ đề."""
    is_valid: bool = Field(..., description="True nếu không có lỗi nghiêm trọng (ERROR)")
    total_segments: int = Field(..., ge=0)
    errors_count: int = Field(0, ge=0)
    warnings_count: int = Field(0, ge=0)
    issues: List[ValidationIssue] = Field(default_factory=list)


class SubtitleDocument(BaseModel):
    """Tài liệu phụ đề đầy đủ có quản lý phiên bản."""
    schema_version: str = "1.0.0"
    item_id: str
    dedup_key: str
    audio_hash: str
    asr_model: str
    translation_model: str
    segments: List[SubtitleSegment] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    modified_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

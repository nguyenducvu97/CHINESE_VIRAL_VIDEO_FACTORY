"""Unit tests for SRTEngine formatting, parsing, validation, and editing."""

import pytest
from src.subtitle.models import SubtitleDocument, SubtitleSegment
from src.subtitle.srt_engine import SRTEngine, ms_to_srt_time, srt_time_to_ms


def test_timestamp_conversions():
    """Verify bidirectional millisecond <-> SRT timestamp conversions."""
    assert ms_to_srt_time(0) == "00:00:00,000"
    assert ms_to_srt_time(15234) == "00:00:15,234"
    assert ms_to_srt_time(3661005) == "01:01:01,005"

    assert srt_time_to_ms("00:00:00,000") == 0
    assert srt_time_to_ms("00:00:15,234") == 15234
    assert srt_time_to_ms("01:01:01.005") == 3661005


def test_export_and_parse_srt():
    """Verify SRT export and parse round-trip preserves timing and text."""
    segments = [
        SubtitleSegment(
            index=1,
            start_ms=1000,
            end_ms=4500,
            text_zh="第一句话",
            text_vi="Câu thoại thứ nhất",
        ),
        SubtitleSegment(
            index=2,
            start_ms=4800,
            end_ms=8000,
            text_zh="第二句话",
            text_vi="Câu thoại thứ hai",
        ),
    ]

    srt_str = SRTEngine.export_srt(segments)
    assert "00:00:01,000 --> 00:00:04,500" in srt_str
    assert "Câu thoại thứ nhất" in srt_str

    parsed = SRTEngine.parse_srt(srt_str)
    assert len(parsed) == 2
    assert parsed[0].start_ms == 1000
    assert parsed[0].end_ms == 4500
    assert parsed[0].text_vi == "Câu thoại thứ nhất"


def test_validate_subtitles_clean():
    """Verify valid subtitles pass with zero errors or warnings."""
    segments = [
        SubtitleSegment(
            index=1,
            start_ms=1000,
            end_ms=3000,
            text_zh="正常文本",
            text_vi="Đoạn thoại bình thường ngắn gọn.",
        ),
        SubtitleSegment(
            index=2,
            start_ms=3200,
            end_ms=5000,
            text_zh="第二句",
            text_vi="Đoạn thoại tiếp theo.",
        ),
    ]

    report = SRTEngine.validate_subtitles(segments)
    assert report.is_valid is True
    assert report.errors_count == 0
    assert report.warnings_count == 0


def test_validate_subtitles_with_errors_and_warnings():
    """Verify detector catches timestamp overlap, invalid duration, empty text, and long lines."""
    segments = [
        # Segment 1: Line too long (> 42 chars) -> Warning
        SubtitleSegment(
            index=1,
            start_ms=1000,
            end_ms=4000,
            text_zh="超长文本",
            text_vi="Đây là một câu phụ đề tiếng Việt rất dài vượt quá giới hạn khuyến nghị cho màn hình điện thoại di động.",
        ),
        # Segment 2: Overlaps with Segment 1 (start 3500 < end 4000) -> Error
        SubtitleSegment(
            index=2,
            start_ms=3500,
            end_ms=6000,
            text_zh="重叠",
            text_vi="Trùng thời gian",
        ),
        # Segment 3: Empty text -> Error
        SubtitleSegment(
            index=3,
            start_ms=6500,
            end_ms=8000,
            text_zh="空",
            text_vi="   ",
        ),
    ]

    report = SRTEngine.validate_subtitles(segments, max_chars_per_line=42)
    assert report.is_valid is False
    assert report.errors_count >= 2
    assert report.warnings_count >= 1

    issue_codes = [issue.issue_code for issue in report.issues]
    assert "ERR_TIMESTAMP_OVERLAP" in issue_codes
    assert "ERR_EMPTY_SUBTITLE" in issue_codes
    assert "WARN_LINE_TOO_LONG" in issue_codes


def test_edit_segment():
    """Verify in-place subtitle editing."""
    doc = SubtitleDocument(
        item_id="item_1",
        dedup_key="bilibili:BV100",
        audio_hash="hash123",
        asr_model="test-asr",
        translation_model="test-trans",
        segments=[
            SubtitleSegment(
                index=1,
                start_ms=1000,
                end_ms=3000,
                text_zh="原始中文",
                text_vi="Bản dịch cũ",
            )
        ],
    )

    updated_doc = SRTEngine.edit_segment(doc, index=1, new_text_vi="Bản dịch đã chỉnh sửa hoàn hảo!")
    assert updated_doc.segments[0].text_vi == "Bản dịch đã chỉnh sửa hoàn hảo!"

"""SRT Engine: Formatting, Parsing, Validation, and In-place Editing."""

from datetime import datetime, timezone
import re
from typing import List, Optional

from src.subtitle.models import (
    SubtitleDocument,
    SubtitleSegment,
    SubtitleValidationReport,
    ValidationIssue,
)


def ms_to_srt_time(ms: int) -> str:
    """Convert millisecond integer into standard SRT timestamp format: HH:MM:SS,mmm."""
    if ms < 0:
        ms = 0
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def srt_time_to_ms(ts_str: str) -> int:
    """Parse standard SRT timestamp (HH:MM:SS,mmm or HH:MM:SS.mmm) into milliseconds."""
    clean_ts = ts_str.strip().replace(".", ",")
    parts = clean_ts.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid SRT timestamp format: {ts_str}")
    hours = int(parts[0])
    minutes = int(parts[1])
    sec_parts = parts[2].split(",")
    seconds = int(sec_parts[0])
    milliseconds = int(sec_parts[1]) if len(sec_parts) > 1 else 0
    return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds


class SRTEngine:
    """Engine responsible for exporting, parsing, validating, and editing subtitles."""

    @staticmethod
    def export_srt(segments: List[SubtitleSegment], bilingual: bool = False) -> str:
        """Export subtitle segments to standard UTF-8 SRT string."""
        blocks = []
        for seg in segments:
            start_str = ms_to_srt_time(seg.start_ms)
            end_str = ms_to_srt_time(seg.end_ms)
            if bilingual and seg.text_zh:
                content = f"{seg.text_vi}\n{seg.text_zh}"
            else:
                content = seg.text_vi

            block = f"{seg.index}\n{start_str} --> {end_str}\n{content}"
            blocks.append(block)

        return "\n\n".join(blocks) + "\n"

    @staticmethod
    def parse_srt(srt_content: str) -> List[SubtitleSegment]:
        """Parse standard SRT string into structured SubtitleSegment list."""
        segments: List[SubtitleSegment] = []
        raw_blocks = re.split(r"\n\s*\n", srt_content.strip())

        for block in raw_blocks:
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if len(lines) < 3:
                continue

            try:
                index = int(lines[0])
            except ValueError:
                continue

            time_match = re.match(
                r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})",
                lines[1],
            )
            if not time_match:
                continue

            start_ms = srt_time_to_ms(time_match.group(1))
            end_ms = srt_time_to_ms(time_match.group(2))
            text_lines = lines[2:]
            text_vi = text_lines[0]
            text_zh = text_lines[1] if len(text_lines) > 1 else ""

            segments.append(
                SubtitleSegment(
                    index=index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text_zh=text_zh,
                    text_vi=text_vi,
                )
            )

        return segments

    @staticmethod
    def validate_subtitles(
        segments: List[SubtitleSegment],
        max_chars_per_line: int = 42,
    ) -> SubtitleValidationReport:
        """Thoroughly validate subtitle timing, collisions, empty lines, and lengths."""
        issues: List[ValidationIssue] = []
        errors_count = 0
        warnings_count = 0

        prev_end_ms = -1

        for seg in segments:
            # 1. Check positive duration
            if seg.end_ms <= seg.start_ms:
                issues.append(
                    ValidationIssue(
                        level="ERROR",
                        segment_index=seg.index,
                        issue_code="ERR_INVALID_DURATION",
                        message=f"Thời gian kết thúc ({seg.end_ms}ms) nhỏ hơn hoặc bằng thời gian bắt đầu ({seg.start_ms}ms)",
                    )
                )
                errors_count += 1

            # 2. Check timestamp overlap
            if prev_end_ms > 0 and seg.start_ms < prev_end_ms:
                overlap = prev_end_ms - seg.start_ms
                issues.append(
                    ValidationIssue(
                        level="ERROR",
                        segment_index=seg.index,
                        issue_code="ERR_TIMESTAMP_OVERLAP",
                        message=f"Thời gian bắt đầu chồng chéo với phân đoạn trước đó {overlap}ms",
                    )
                )
                errors_count += 1

            # 3. Check empty texts
            if not seg.text_vi.strip():
                issues.append(
                    ValidationIssue(
                        level="ERROR",
                        segment_index=seg.index,
                        issue_code="ERR_EMPTY_SUBTITLE",
                        message="Lời thoại tiếng Việt rỗng",
                    )
                )
                errors_count += 1

            # 4. Check maximum line length
            for line in seg.text_vi.split("\n"):
                if len(line) > max_chars_per_line:
                    issues.append(
                        ValidationIssue(
                            level="WARNING",
                            segment_index=seg.index,
                            issue_code="WARN_LINE_TOO_LONG",
                            message=f"Độ dài dòng ({len(line)} ký tự) vượt ngưỡng khuyến nghị ({max_chars_per_line} ký tự)",
                        )
                    )
                    warnings_count += 1

            prev_end_ms = seg.end_ms

        return SubtitleValidationReport(
            is_valid=(errors_count == 0),
            total_segments=len(segments),
            errors_count=errors_count,
            warnings_count=warnings_count,
            issues=issues,
        )

    @staticmethod
    def edit_segment(
        doc: SubtitleDocument,
        index: int,
        new_text_vi: Optional[str] = None,
        new_start_ms: Optional[int] = None,
        new_end_ms: Optional[int] = None,
    ) -> SubtitleDocument:
        """Allow manual editing of translated subtitle segments."""
        updated_segments = []
        found = False

        for seg in doc.segments:
            if seg.index == index:
                found = True
                updated_seg = SubtitleSegment(
                    index=seg.index,
                    start_ms=new_start_ms if new_start_ms is not None else seg.start_ms,
                    end_ms=new_end_ms if new_end_ms is not None else seg.end_ms,
                    text_zh=seg.text_zh,
                    text_vi=new_text_vi if new_text_vi is not None else seg.text_vi,
                    speaker=seg.speaker,
                )
                updated_segments.append(updated_seg)
            else:
                updated_segments.append(seg)

        if not found:
            raise IndexError(f"Subtitle segment with index {index} not found in document")

        doc.segments = updated_segments
        doc.modified_at = datetime.now(timezone.utc).isoformat()
        return doc

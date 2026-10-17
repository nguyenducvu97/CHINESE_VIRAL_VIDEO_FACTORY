"""Video Quality Control Validator using native FFprobe and FFmpeg."""

import json
import logging
import math
from pathlib import Path
import subprocess
from typing import Optional

from src.subtitle.demuxer import compute_file_sha256
from src.rendering.models import VideoQCInspection

logger = logging.getLogger(__name__)


def _compute_aspect_ratio(w: int, h: int) -> str:
    """Calculate simplified aspect ratio string e.g. 16:9, 9:16, 4:3."""
    if w <= 0 or h <= 0:
        return "unknown"
    gcd = math.gcd(w, h)
    simpl_w = w // gcd
    simpl_h = h // gcd
    # Common mappings
    if (simpl_w, simpl_h) in [(16, 9), (9, 16), (4, 3), (3, 4), (1, 1)]:
        return f"{simpl_w}:{simpl_h}"
    ratio = w / float(h)
    if abs(ratio - 16 / 9) < 0.05:
        return "16:9"
    if abs(ratio - 9 / 16) < 0.05:
        return "9:16"
    return f"{simpl_w}:{simpl_h}"


class VideoQCValidator:
    """Performs deep automated inspection on rendered videos to ensure zero defects."""

    def __init__(self, ffprobe_bin: str = "ffprobe", ffmpeg_bin: str = "ffmpeg"):
        self.ffprobe_bin = ffprobe_bin
        self.ffmpeg_bin = ffmpeg_bin

    def inspect_video(
        self,
        video_path: Path,
        source_video_path: Optional[Path] = None,
    ) -> VideoQCInspection:
        """Inspect video file properties, codecs, playability, and integrity."""
        issues = []
        if not video_path.exists():
            return VideoQCInspection(
                is_valid=False,
                width=1,
                height=1,
                aspect_ratio="unknown",
                video_codec="none",
                duration_seconds=0.0,
                file_size_bytes=0,
                is_playable=False,
                checksum_sha256="",
                issues=["Tệp video không tồn tại trên hệ thống"],
            )

        file_size = video_path.stat().st_size
        if file_size == 0:
            issues.append("Tệp video rỗng (0 bytes)")

        # 1. Run FFprobe to extract metadata
        cmd = [
            self.ffprobe_bin,
            "-v", "error",
            "-show_entries", "stream=codec_name,codec_type,width,height,duration",
            "-show_entries", "format=duration,size",
            "-of", "json",
            str(video_path),
        ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return VideoQCInspection(
                is_valid=False,
                width=1,
                height=1,
                aspect_ratio="unknown",
                video_codec="none",
                duration_seconds=0.0,
                file_size_bytes=file_size,
                is_playable=False,
                checksum_sha256="",
                issues=[f"Lỗi đọc thông tin video bằng ffprobe: {res.stderr}"],
            )

        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        format_info = data.get("format", {})

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not video_stream:
            issues.append("Không tìm thấy luồng hình ảnh (video stream)")
            w, h = 1, 1
            v_codec = "none"
        else:
            w = int(video_stream.get("width", 1))
            h = int(video_stream.get("height", 1))
            v_codec = video_stream.get("codec_name", "unknown")

        a_codec = audio_stream.get("codec_name") if audio_stream else None
        duration = float(format_info.get("duration", 0.0))
        aspect_ratio = _compute_aspect_ratio(w, h)

        # 2. Check playability (stream decoding test)
        play_cmd = [
            self.ffmpeg_bin,
            "-v", "error",
            "-i", str(video_path),
            "-f", "null",
            "-",
        ]
        play_res = subprocess.run(play_cmd, capture_output=True, text=True)
        is_playable = (play_res.returncode == 0)
        if not is_playable:
            issues.append(f"Kiểm tra giải mã video thất bại: {play_res.stderr}")

        # 3. If source video provided, ensure original dimensions are preserved 100%
        if source_video_path and source_video_path.exists():
            source_insp = self.inspect_video(source_video_path)
            if w != source_insp.width or h != source_insp.height:
                issues.append(
                    f"Kích thước khung hình ({w}x{h}) bị biến dạng so với video gốc ({source_insp.width}x{source_insp.height})"
                )

        checksum = compute_file_sha256(video_path)

        return VideoQCInspection(
            is_valid=(len(issues) == 0 and is_playable),
            width=w,
            height=h,
            aspect_ratio=aspect_ratio,
            video_codec=v_codec,
            audio_codec=a_codec,
            duration_seconds=round(duration, 2),
            file_size_bytes=file_size,
            is_playable=is_playable,
            checksum_sha256=checksum,
            issues=issues,
        )

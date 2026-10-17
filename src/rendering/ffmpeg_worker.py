"""FFmpeg Render Worker: Preserves original visual frames and renders Vietsub & Dubbed variants."""

import logging
from pathlib import Path
import shutil
import subprocess
from typing import Optional

from src.core.exceptions import CVVFError
from src.rendering.models import RenderTaskResult, VideoVariantType
from src.rendering.qc_validator import VideoQCValidator

logger = logging.getLogger(__name__)


def escape_ffmpeg_filter_path(file_path: Path) -> str:
    """Escape Windows file paths for FFmpeg subtitle filter (colons and backslashes)."""
    clean_path = str(file_path.resolve()).replace("\\", "/")
    # Escape colon after drive letter: D:/... -> D\:/...
    if len(clean_path) > 1 and clean_path[1] == ":":
        clean_path = clean_path[0] + "\\:" + clean_path[2:]
    return clean_path


class FFmpegRenderWorker:
    """Worker responsible for rendering variants while guaranteeing 100% pixel preservation."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe"):
        self.ffmpeg_bin = ffmpeg_bin
        self.qc = VideoQCValidator(ffprobe_bin=ffprobe_bin, ffmpeg_bin=ffmpeg_bin)

    def export_original_preserved(
        self,
        source_video_path: Path,
        output_dir: Path,
        item_id: str,
        dedup_key: str,
    ) -> RenderTaskResult:
        """Create an immutable, preserved archive copy of the original source video."""
        if not source_video_path.exists():
            raise FileNotFoundError(f"Source video not found: {source_video_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        dest_path = output_dir / f"ORIGINAL_PRESERVED_{item_id}.mp4"

        # Prevent overwriting source if already in destination
        if source_video_path.resolve() != dest_path.resolve():
            shutil.copy2(source_video_path, dest_path)

        qc = self.qc.inspect_video(dest_path)

        return RenderTaskResult(
            item_id=item_id,
            dedup_key=dedup_key,
            variant_type=VideoVariantType.ORIGINAL_PRESERVED,
            output_video_path=str(dest_path),
            checksum_sha256=qc.checksum_sha256,
            qc_inspection=qc,
        )

    def render_vietsub(
        self,
        source_video_path: Path,
        srt_path: Path,
        output_dir: Path,
        item_id: str,
        dedup_key: str,
        hardsub: bool = False,
    ) -> RenderTaskResult:
        """Render Vietsub MP4 variant.
        
        Args:
            source_video_path: Original video.
            srt_path: Subtitle SRT file.
            output_dir: Target directory.
            hardsub: When True, burns subtitles into video frames. When False, soft-muxes into MP4 stream.
        """
        if not source_video_path.exists():
            raise FileNotFoundError(f"Source video not found: {source_video_path}")
        if not srt_path.exists():
            raise FileNotFoundError(f"Subtitle file not found: {srt_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        out_video = output_dir / f"VIETSUB_{item_id}.mp4"

        if hardsub:
            # Burn-in subtitles while maintaining exact resolution and aspect ratio
            escaped_srt = escape_ffmpeg_filter_path(srt_path)
            cmd = [
                self.ffmpeg_bin, "-y",
                "-i", str(source_video_path),
                "-vf", f"subtitles='{escaped_srt}'",
                "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                "-c:a", "copy",
                str(out_video),
            ]
        else:
            # Softsub mux: keeps 100% untouched video stream (-c:v copy)
            cmd = [
                self.ffmpeg_bin, "-y",
                "-i", str(source_video_path),
                "-i", str(srt_path),
                "-c:v", "copy",
                "-c:a", "copy",
                "-c:s", "mov_text",
                "-metadata:s:s:0", "language=vie",
                str(out_video),
            ]

        logger.info(f"Rendering Vietsub video (hardsub={hardsub})...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise CVVFError(f"Rendering Vietsub failed: {res.stderr}")

        qc = self.qc.inspect_video(out_video, source_video_path=source_video_path)

        return RenderTaskResult(
            item_id=item_id,
            dedup_key=dedup_key,
            variant_type=VideoVariantType.VIETSUB,
            output_video_path=str(out_video),
            checksum_sha256=qc.checksum_sha256,
            qc_inspection=qc,
        )

    def render_dubbed_vietsub(
        self,
        source_video_path: Path,
        dubbed_audio_path: Path,
        output_dir: Path,
        item_id: str,
        dedup_key: str,
        srt_path: Optional[Path] = None,
        hardsub: bool = False,
    ) -> RenderTaskResult:
        """Render Dubbed + Vietsub variant with original video stream and mixed Vietnamese audio."""
        if not source_video_path.exists():
            raise FileNotFoundError(f"Source video not found: {source_video_path}")
        if not dubbed_audio_path.exists():
            raise FileNotFoundError(f"Dubbed audio not found: {dubbed_audio_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        out_video = output_dir / f"DUBBED_VIETSUB_{item_id}.mp4"

        inputs = ["-i", str(source_video_path), "-i", str(dubbed_audio_path)]
        maps = ["-map", "0:v:0", "-map", "1:a:0"]

        if srt_path and srt_path.exists():
            if hardsub:
                escaped_srt = escape_ffmpeg_filter_path(srt_path)
                cmd = [
                    self.ffmpeg_bin, "-y",
                    "-i", str(source_video_path),
                    "-i", str(dubbed_audio_path),
                    "-vf", f"subtitles='{escaped_srt}'",
                    "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                    "-c:a", "aac", "-b:a", "192k",
                    "-map", "0:v:0", "-map", "1:a:0",
                    str(out_video),
                ]
            else:
                inputs.extend(["-i", str(srt_path)])
                maps.extend(["-map", "2:s:0"])
                cmd = [
                    self.ffmpeg_bin, "-y"
                ] + inputs + [
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k",
                    "-c:s", "mov_text",
                    "-metadata:s:s:0", "language=vie"
                ] + maps + [str(out_video)]
        else:
            # Video stream copied directly, audio replaced with dubbed track
            cmd = [
                self.ffmpeg_bin, "-y"
            ] + inputs + [
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k"
            ] + maps + [str(out_video)]

        logger.info(f"Rendering Dubbed Vietsub video...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise CVVFError(f"Rendering Dubbed Vietsub failed: {res.stderr}")

        qc = self.qc.inspect_video(out_video, source_video_path=source_video_path)

        return RenderTaskResult(
            item_id=item_id,
            dedup_key=dedup_key,
            variant_type=VideoVariantType.DUBBED_VIETSUB,
            output_video_path=str(out_video),
            checksum_sha256=qc.checksum_sha256,
            qc_inspection=qc,
        )

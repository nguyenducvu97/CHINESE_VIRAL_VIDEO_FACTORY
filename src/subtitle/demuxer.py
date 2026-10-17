"""Audio Demuxer: Extracts audio track from video files using local FFmpeg."""

import hashlib
import logging
from pathlib import Path
import subprocess
from typing import Optional

from src.core.exceptions import CVVFError

logger = logging.getLogger(__name__)


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class AudioDemuxer:
    """Extracts 16kHz mono WAV audio tracks from source videos using native FFmpeg."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

    def extract_audio(
        self,
        video_path: Path,
        output_audio_path: Optional[Path] = None,
        sample_rate: int = 16000,
    ) -> Path:
        """Extract audio track from video file.
        
        Args:
            video_path: Path to source video file.
            output_audio_path: Destination path for WAV file. If None, derives from video name.
            sample_rate: Target sample rate in Hz (default 16000 for ASR).
            
        Returns:
            Path to extracted WAV audio file.
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Source video not found: {video_path}")

        if output_audio_path is None:
            output_audio_path = video_path.with_suffix(".wav")

        output_audio_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_bin,
            "-y",  # Overwrite output without prompting
            "-i", str(video_path),
            "-vn",  # Disable video stream
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", "1",  # Mono channel for ASR
            str(output_audio_path),
        ]

        logger.info(f"Extracting audio using FFmpeg: {' '.join(cmd)}")
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                raise CVVFError(f"FFmpeg audio extraction failed (code {res.returncode}): {res.stderr}")

            if not output_audio_path.exists() or output_audio_path.stat().st_size == 0:
                raise CVVFError(f"Extracted audio file is missing or 0 bytes: {output_audio_path}")

            logger.info(f"Audio extracted successfully: {output_audio_path} ({output_audio_path.stat().st_size} bytes)")
            return output_audio_path

        except FileNotFoundError:
            raise CVVFError(f"FFmpeg binary '{self.ffmpeg_bin}' not found on system PATH")

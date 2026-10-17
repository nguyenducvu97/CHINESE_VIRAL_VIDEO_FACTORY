"""Integration tests for AudioDemuxer using native FFmpeg."""

import subprocess
import pytest
from pathlib import Path
from src.subtitle.demuxer import AudioDemuxer, compute_file_sha256


@pytest.fixture
def sample_video_with_audio(tmp_path: Path) -> Path:
    """Generate a 1-second test MP4 file with synthetic video & sine audio using FFmpeg."""
    video_path = tmp_path / "synthetic_test_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"FFmpeg synthetic video creation failed: {res.stderr}"
    assert video_path.exists() and video_path.stat().st_size > 0
    return video_path


def test_audio_demuxer_extract_and_hash(sample_video_with_audio: Path, tmp_path: Path):
    """Verify AudioDemuxer extracts 16kHz mono WAV from video and computes hash."""
    demuxer = AudioDemuxer()
    out_wav = tmp_path / "extracted_audio.wav"

    result_path = demuxer.extract_audio(
        video_path=sample_video_with_audio,
        output_audio_path=out_wav,
        sample_rate=16000,
    )

    assert result_path.exists()
    assert result_path.stat().st_size > 0
    assert result_path == out_wav

    # Compute hash
    audio_hash = compute_file_sha256(result_path)
    assert len(audio_hash) == 64  # SHA-256 length

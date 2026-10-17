"""Unit & Integration tests for FFmpegRenderWorker and VideoQCValidator."""

from pathlib import Path
import subprocess
import pytest

from src.rendering.ffmpeg_worker import FFmpegRenderWorker, escape_ffmpeg_filter_path
from src.rendering.models import VideoVariantType
from src.rendering.qc_validator import VideoQCValidator


@pytest.fixture
def synthetic_source_video(tmp_path: Path) -> Path:
    """Generate a 2-second 320x240 25fps MP4 video with sine audio."""
    video_path = tmp_path / "original_source_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"FFmpeg failed: {res.stderr}"
    return video_path


@pytest.fixture
def sample_srt_file(tmp_path: Path) -> Path:
    """Create a sample SRT file for rendering tests."""
    srt_path = tmp_path / "sample.srt"
    srt_content = (
        "1\n"
        "00:00:00,200 --> 00:00:01,800\n"
        "Thử nghiệm phụ đề tiếng Việt\n\n"
    )
    srt_path.write_text(srt_content, encoding="utf-8")
    return srt_path


def test_escape_ffmpeg_filter_path():
    """Verify Windows colon escaping for FFmpeg subtitle filter."""
    p = Path("D:/test/path/sample.srt")
    escaped = escape_ffmpeg_filter_path(p)
    assert "\\:" in escaped
    assert "/" in escaped


def test_export_original_preserved(synthetic_source_video: Path, tmp_path: Path):
    """Verify original video is preserved without alteration."""
    worker = FFmpegRenderWorker()
    out_dir = tmp_path / "output_preserved"

    res = worker.export_original_preserved(
        source_video_path=synthetic_source_video,
        output_dir=out_dir,
        item_id="item_001",
        dedup_key="bilibili:BV_001",
    )

    assert res.variant_type == VideoVariantType.ORIGINAL_PRESERVED
    assert Path(res.output_video_path).exists()
    assert res.qc_inspection.is_valid is True
    assert res.qc_inspection.width == 320
    assert res.qc_inspection.height == 240
    assert res.qc_inspection.is_playable is True


def test_render_vietsub_softsub(
    synthetic_source_video: Path, sample_srt_file: Path, tmp_path: Path
):
    """Verify rendering Vietsub variant with softsub muxing."""
    worker = FFmpegRenderWorker()
    out_dir = tmp_path / "output_vietsub"

    res = worker.render_vietsub(
        source_video_path=synthetic_source_video,
        srt_path=sample_srt_file,
        output_dir=out_dir,
        item_id="item_002",
        dedup_key="bilibili:BV_002",
        hardsub=False,
    )

    assert res.variant_type == VideoVariantType.VIETSUB
    assert Path(res.output_video_path).exists()
    assert res.qc_inspection.is_valid is True
    assert res.qc_inspection.width == 320
    assert res.qc_inspection.height == 240
    assert res.qc_inspection.is_playable is True


def test_render_dubbed_vietsub(
    synthetic_source_video: Path, sample_srt_file: Path, tmp_path: Path
):
    """Verify rendering Dubbed + Vietsub variant with new audio and subtitles."""
    # Generate 2-second replacement audio WAV
    dubbed_audio = tmp_path / "dubbed_voice.wav"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(dubbed_audio),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    worker = FFmpegRenderWorker()
    out_dir = tmp_path / "output_dubbed"

    res = worker.render_dubbed_vietsub(
        source_video_path=synthetic_source_video,
        dubbed_audio_path=dubbed_audio,
        srt_path=sample_srt_file,
        output_dir=out_dir,
        item_id="item_003",
        dedup_key="bilibili:BV_003",
        hardsub=False,
    )

    assert res.variant_type == VideoVariantType.DUBBED_VIETSUB
    assert Path(res.output_video_path).exists()
    assert res.qc_inspection.is_valid is True
    assert res.qc_inspection.audio_codec == "aac"
    assert res.qc_inspection.width == 320
    assert res.qc_inspection.height == 240
    assert res.qc_inspection.is_playable is True

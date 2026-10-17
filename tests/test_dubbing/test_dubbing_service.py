"""Unit tests for DubbingService."""

import math
from pathlib import Path
import struct
import wave
import pytest

from src.dubbing.adapters.mock_tts import MockTTSAdapter
from src.dubbing.models import VoiceGender, VoiceProfile
from src.dubbing.service import DubbingService
from src.subtitle.models import SubtitleDocument, SubtitleSegment


def _create_wav(path: Path, duration_sec: float, sample_rate: int = 16000):
    path.parent.mkdir(parents=True, exist_ok=True)
    total_samples = int(sample_rate * duration_sec)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(total_samples):
            val = int(8000 * math.sin(2 * math.pi * 440.0 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)


def test_dubbing_service_complete_flow(tmp_path: Path):
    """Verify complete dubbing pipeline with SubtitleDocument and original audio."""
    original_audio = tmp_path / "original_bgm.wav"
    _create_wav(original_audio, duration_sec=5.0)

    doc = SubtitleDocument(
        item_id="item_dub_01",
        dedup_key="bilibili:BV_DUB_01",
        audio_hash="testhash123",
        asr_model="mock-asr",
        translation_model="mock-trans",
        segments=[
            SubtitleSegment(
                index=1,
                start_ms=500,
                end_ms=2500,
                text_zh="第一句测试",
                text_vi="Câu thoại thứ nhất",
            ),
            SubtitleSegment(
                index=2,
                start_ms=2800,
                end_ms=4500,
                text_zh="第二句测试",
                text_vi="Câu thoại thứ hai tiếp theo",
            ),
        ],
    )

    out_dir = tmp_path / "dubbing_out"
    service = DubbingService(
        tts_adapter=MockTTSAdapter(),
        cache_dir=tmp_path / "tts_cache",
    )

    voice = VoiceProfile(
        voice_id="mock-voice",
        gender=VoiceGender.FEMALE,
        display_name="Mock Voice",
        provider="mock",
    )

    result = service.dub_video(
        subtitle_doc=doc,
        original_audio_path=original_audio,
        output_dir=out_dir,
        voice_profile=voice,
        total_duration_ms=5000,
    )

    assert Path(result.mixed_audio_path).exists()
    assert len(result.segments) == 2
    assert result.qc_report.is_passed is True
    assert result.cost == 0.0
    assert len(result.qc_report.limitations) > 0
    assert "Ducking" in result.qc_report.limitations[0]

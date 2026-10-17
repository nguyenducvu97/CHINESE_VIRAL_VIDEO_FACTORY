"""Unit tests for MockTTSAdapter."""

from pathlib import Path
import wave
import pytest

from src.dubbing.adapters.mock_tts import MockTTSAdapter
from src.dubbing.models import VoiceGender, VoiceProfile


def test_mock_tts_synthesis(tmp_path: Path):
    """Verify MockTTSAdapter generates valid 16kHz PCM WAV files."""
    adapter = MockTTSAdapter()
    voice = VoiceProfile(
        voice_id="mock-female",
        gender=VoiceGender.FEMALE,
        display_name="Mock Female Voice",
        provider="mock",
    )
    out_wav = tmp_path / "mock_speech.wav"
    adapter.synthesize(text="Xin chào mọi người đây là bản thử nghiệm", voice=voice, output_path=out_wav)

    assert out_wav.exists()
    assert out_wav.stat().st_size > 0

    with wave.open(str(out_wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        duration = wf.getnframes() / float(wf.getframerate())
        assert duration >= 1.0

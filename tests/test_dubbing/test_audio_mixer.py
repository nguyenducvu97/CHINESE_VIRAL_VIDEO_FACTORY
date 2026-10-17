"""Unit tests for AudioMixer and AudioQualityChecker."""

import math
from pathlib import Path
import struct
import wave
import pytest

from src.dubbing.audio_mixer import AudioMixer, AudioQualityChecker
from src.dubbing.models import DubbedSegment


def _create_wav(path: Path, duration_sec: float, freq: float = 440.0, sample_rate: int = 16000):
    path.parent.mkdir(parents=True, exist_ok=True)
    total_samples = int(sample_rate * duration_sec)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(total_samples):
            val = int(8000 * math.sin(2 * math.pi * freq * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)


def test_audio_mixer_assemble_speech(tmp_path: Path):
    """Verify assembling multiple speech segments into a single canvas track."""
    mixer = AudioMixer()
    seg1_path = tmp_path / "seg1.wav"
    seg2_path = tmp_path / "seg2.wav"
    _create_wav(seg1_path, duration_sec=1.0)
    _create_wav(seg2_path, duration_sec=1.5)

    segments = [
        DubbedSegment(
            index=1,
            start_ms=500,
            end_ms=1500,
            target_duration_ms=1000,
            actual_duration_ms=1000,
            tempo_factor=1.0,
            text_vi="Đoạn 1",
            audio_path=str(seg1_path),
        ),
        DubbedSegment(
            index=2,
            start_ms=2000,
            end_ms=3500,
            target_duration_ms=1500,
            actual_duration_ms=1500,
            tempo_factor=1.0,
            text_vi="Đoạn 2",
            audio_path=str(seg2_path),
        ),
    ]

    out_speech = tmp_path / "assembled.wav"
    mixer.assemble_speech_track(segments=segments, total_duration_ms=4000, output_speech_path=out_speech)

    assert out_speech.exists()
    assert out_speech.stat().st_size > 0


def test_audio_quality_checker_clean(tmp_path: Path):
    """Verify clean audio passes QC checks."""
    clean_wav = tmp_path / "clean.wav"
    _create_wav(clean_wav, duration_sec=2.0)

    qc = AudioQualityChecker()
    report = qc.check_audio(clean_wav, expected_duration_ms=2000, drift_tolerance_ms=200)

    assert report.is_passed is True
    assert report.is_silent is False
    assert report.is_clipping is False
    assert report.drift_ms <= 200

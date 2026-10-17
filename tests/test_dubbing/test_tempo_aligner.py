"""Unit tests for SpeechTempoAligner."""

import math
from pathlib import Path
import struct
import wave
import pytest

from src.dubbing.tempo_aligner import SpeechTempoAligner, get_wav_duration_ms


def _create_sine_wav(path: Path, duration_sec: float, sample_rate: int = 16000):
    path.parent.mkdir(parents=True, exist_ok=True)
    total_samples = int(sample_rate * duration_sec)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(total_samples):
            val = int(10000 * math.sin(2 * math.pi * 440.0 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(frames)


def test_tempo_aligner_speed_up(tmp_path: Path):
    """Verify audio is sped up when longer than target duration."""
    input_wav = tmp_path / "long_audio.wav"
    _create_sine_wav(input_wav, duration_sec=3.0)  # 3000ms
    assert get_wav_duration_ms(input_wav) == 3000

    aligner = SpeechTempoAligner(min_tempo=0.85, max_tempo=1.25)
    out_wav = tmp_path / "speedup_audio.wav"

    # Target is 2500ms (requires ~1.2x speed)
    tempo = aligner.align_tempo(
        input_audio_path=input_wav,
        target_duration_ms=2500,
        output_audio_path=out_wav,
    )

    assert tempo == 1.2
    new_duration = get_wav_duration_ms(out_wav)
    assert abs(new_duration - 2500) < 100


def test_tempo_aligner_clamped_bounds(tmp_path: Path):
    """Verify extreme ratios are clamped to prevent voice distortion."""
    input_wav = tmp_path / "very_long_audio.wav"
    _create_sine_wav(input_wav, duration_sec=4.0)  # 4000ms

    aligner = SpeechTempoAligner(min_tempo=0.85, max_tempo=1.25)
    out_wav = tmp_path / "clamped_audio.wav"

    # Target is 2000ms (would require 2.0x speed, should clamp at 1.25)
    tempo = aligner.align_tempo(
        input_audio_path=input_wav,
        target_duration_ms=2000,
        output_audio_path=out_wav,
    )

    assert tempo == 1.25

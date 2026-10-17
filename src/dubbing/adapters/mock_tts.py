"""Deterministic Mock TTS Adapter for testing and offline execution."""

import math
from pathlib import Path
import struct
import wave

from src.dubbing.adapters.base_tts import BaseTTSAdapter
from src.dubbing.models import VoiceProfile


class MockTTSAdapter(BaseTTSAdapter):
    """Mock TTS generator producing valid PCM WAV files without network access."""

    def __init__(self, provider_name: str = "mock-tts"):
        super().__init__(provider_name=provider_name)

    def synthesize(
        self,
        text: str,
        voice: VoiceProfile,
        output_path: Path,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Estimate duration based on word count (~250ms per syllable/word, minimum 1.0s)
        words = text.split()
        duration_sec = max(len(words) * 0.25, 1.0)

        sample_rate = 16000
        total_samples = int(sample_rate * duration_sec)
        frequency = 300.0 if voice.gender.value == "FEMALE" else 150.0

        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)

            # Generate gentle sine tone simulating speech acoustic presence
            frames = bytearray()
            for i in range(total_samples):
                # Apply envelope to prevent pop/click
                envelope = min(i / (sample_rate * 0.05), (total_samples - i) / (sample_rate * 0.05), 1.0)
                sample = int(12000 * envelope * math.sin(2 * math.pi * frequency * i / sample_rate))
                frames.extend(struct.pack("<h", sample))

            wav_file.writeframes(frames)

        return output_path

"""Speech Tempo Aligner: Matches synthesized Vietnamese speech duration to target subtitle timing."""

import logging
from pathlib import Path
import subprocess
import wave

from src.core.exceptions import CVVFError

logger = logging.getLogger(__name__)


def get_wav_duration_ms(wav_path: Path) -> int:
    """Read precise duration of WAV file in milliseconds."""
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return int((frames / float(rate)) * 1000)


class SpeechTempoAligner:
    """Adjusts speech tempo using FFmpeg atempo filter within natural limits (0.85x - 1.25x)."""

    def __init__(
        self,
        min_tempo: float = 0.85,
        max_tempo: float = 1.25,
        ffmpeg_bin: str = "ffmpeg",
    ):
        self.min_tempo = min_tempo
        self.max_tempo = max_tempo
        self.ffmpeg_bin = ffmpeg_bin

    def align_tempo(
        self,
        input_audio_path: Path,
        target_duration_ms: int,
        output_audio_path: Path,
    ) -> float:
        """Stretch or compress audio duration to fit target subtitle timing.
        
        Args:
            input_audio_path: Path to original TTS audio WAV.
            target_duration_ms: Target duration in milliseconds.
            output_audio_path: Target path for tempo-adjusted WAV.
            
        Returns:
            The actual tempo factor applied (e.g. 1.15).
        """
        if not input_audio_path.exists():
            raise FileNotFoundError(f"Input audio not found: {input_audio_path}")

        actual_duration_ms = get_wav_duration_ms(input_audio_path)
        if target_duration_ms <= 0 or actual_duration_ms <= 0:
            raise ValueError(f"Invalid duration: actual={actual_duration_ms}ms, target={target_duration_ms}ms")

        # Ratio: how fast we need to play it to fit target
        raw_ratio = actual_duration_ms / float(target_duration_ms)

        # If already within 5% of target, keep at 1.0 (no distortion needed)
        if 0.95 <= raw_ratio <= 1.05:
            tempo = 1.0
        else:
            # Clamp within safe limits to preserve natural human voice
            tempo = max(self.min_tempo, min(raw_ratio, self.max_tempo))

        tempo = round(tempo, 3)

        if tempo == 1.0:
            # Just copy / convert
            output_audio_path.write_bytes(input_audio_path.read_bytes())
            return 1.0

        output_audio_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(input_audio_path),
            "-filter:a", f"atempo={tempo}",
            str(output_audio_path),
        ]

        logger.info(f"Applying tempo adjustment: tempo={tempo} (raw_ratio={raw_ratio:.2f})")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise CVVFError(f"FFmpeg atempo failed: {res.stderr}")

        return tempo

"""Edge TTS Adapter synthesizing Vietnamese natural neural voices."""

import asyncio
import logging
from pathlib import Path
import subprocess

import edge_tts

from src.core.exceptions import CVVFError
from src.dubbing.adapters.base_tts import BaseTTSAdapter
from src.dubbing.models import VoiceProfile

logger = logging.getLogger(__name__)


class EdgeTTSAdapter(BaseTTSAdapter):
    """Synthesizes high-quality Vietnamese speech using Microsoft Edge Neural TTS."""

    def __init__(self, provider_name: str = "edge-tts", ffmpeg_bin: str = "ffmpeg"):
        super().__init__(provider_name=provider_name)
        self.ffmpeg_bin = ffmpeg_bin

    def synthesize(
        self,
        text: str,
        voice: VoiceProfile,
        output_path: Path,
    ) -> Path:
        """Synthesize Vietnamese text into WAV file."""
        if not text.strip():
            raise ValueError("TTS text cannot be empty")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_mp3 = output_path.with_suffix(".temp.mp3")

        async def _synthesize():
            communicate = edge_tts.Communicate(text=text, voice=voice.voice_id)
            await communicate.save(str(temp_mp3))

        try:
            # Run async edge-tts in sync context
            asyncio.run(_synthesize())
        except Exception as e:
            logger.error(f"EdgeTTS synthesis failed: {e}")
            raise CVVFError(f"EdgeTTS failed for text '{text[:30]}...': {e}")

        # Convert MP3 to standard 16kHz mono PCM WAV via FFmpeg
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(temp_mp3),
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)

        # Cleanup temp MP3
        if temp_mp3.exists():
            temp_mp3.unlink()

        if res.returncode != 0:
            raise CVVFError(f"FFmpeg conversion from MP3 to WAV failed: {res.stderr}")

        return output_path

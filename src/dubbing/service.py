"""Dubbing Service coordinating TTS synthesis, tempo alignment, and audio mixing."""

import hashlib
import logging
from pathlib import Path
from typing import List, Optional

from src.dubbing.adapters.base_tts import BaseTTSAdapter
from src.dubbing.adapters.mock_tts import MockTTSAdapter
from src.dubbing.audio_mixer import AudioMixer
from src.dubbing.models import (
    AudioQCReport,
    DubbedSegment,
    DubbingResult,
    VoiceGender,
    VoiceProfile,
)
from src.dubbing.tempo_aligner import SpeechTempoAligner, get_wav_duration_ms
from src.subtitle.models import SubtitleDocument

logger = logging.getLogger(__name__)

DEFAULT_FEMALE_VOICE = VoiceProfile(
    voice_id="vi-VN-HoaiMyNeural",
    gender=VoiceGender.FEMALE,
    display_name="Hoài My (Nữ nhẹ nhàng)",
    provider="edge-tts",
)


class DubbingService:
    """Service orchestrating full Vietnamese dubbing workflow."""

    def __init__(
        self,
        tts_adapter: Optional[BaseTTSAdapter] = None,
        aligner: Optional[SpeechTempoAligner] = None,
        mixer: Optional[AudioMixer] = None,
        cache_dir: Optional[Path] = None,
    ):
        self.tts = tts_adapter or MockTTSAdapter()
        self.aligner = aligner or SpeechTempoAligner()
        self.mixer = mixer or AudioMixer()
        self.cache_dir = cache_dir or Path("data/cache/tts")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, text: str, voice_id: str) -> Path:
        """Generate deterministic cache file path for TTS synthesis."""
        key = hashlib.sha256(f"{text}:{voice_id}".encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.wav"

    def dub_video(
        self,
        subtitle_doc: SubtitleDocument,
        original_audio_path: Optional[Path],
        output_dir: Path,
        voice_profile: Optional[VoiceProfile] = None,
        total_duration_ms: Optional[int] = None,
    ) -> DubbingResult:
        """Execute complete dubbing workflow for a SubtitleDocument."""
        voice = voice_profile or DEFAULT_FEMALE_VOICE
        output_dir.mkdir(parents=True, exist_ok=True)

        dubbed_segments: List[DubbedSegment] = []

        # If total_duration_ms not specified, derive from last segment
        if total_duration_ms is None:
            total_duration_ms = (
                max([s.end_ms for s in subtitle_doc.segments]) + 1000
                if subtitle_doc.segments
                else 5000
            )

        # 1. Synthesize and tempo-align each subtitle segment
        for seg in subtitle_doc.segments:
            if not seg.text_vi.strip():
                continue

            target_duration = seg.end_ms - seg.start_ms
            cached_audio = self._get_cache_path(seg.text_vi, voice.voice_id)

            if not cached_audio.exists():
                logger.info(f"Synthesizing segment [{seg.index}]: {seg.text_vi[:30]}...")
                self.tts.synthesize(text=seg.text_vi, voice=voice, output_path=cached_audio)
            else:
                logger.info(f"Using cached TTS for segment [{seg.index}]")

            # Tempo adjustment to fit target segment timing
            aligned_path = output_dir / f"seg_{seg.index}_aligned.wav"
            tempo_applied = self.aligner.align_tempo(
                input_audio_path=cached_audio,
                target_duration_ms=target_duration,
                output_audio_path=aligned_path,
            )

            actual_duration = get_wav_duration_ms(aligned_path)

            dubbed_segments.append(
                DubbedSegment(
                    index=seg.index,
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms,
                    target_duration_ms=target_duration,
                    actual_duration_ms=actual_duration,
                    tempo_factor=tempo_applied,
                    text_vi=seg.text_vi,
                    audio_path=str(aligned_path),
                )
            )

        # 2. Assemble speech canvas track
        speech_track_path = output_dir / "assembled_speech.wav"
        self.mixer.assemble_speech_track(
            segments=dubbed_segments,
            total_duration_ms=total_duration_ms,
            output_speech_path=speech_track_path,
        )

        # 3. Mix speech with original BGM using ducking
        final_mixed_path = output_dir / "final_dubbed_audio.wav"
        mixed_path, qc_report = self.mixer.mix_with_bgm(
            speech_track_path=speech_track_path,
            original_audio_path=original_audio_path,
            output_mixed_path=final_mixed_path,
            total_duration_ms=total_duration_ms,
        )

        return DubbingResult(
            item_id=subtitle_doc.item_id,
            dedup_key=subtitle_doc.dedup_key,
            mixed_audio_path=str(mixed_path),
            voice_profile=voice,
            segments=dubbed_segments,
            qc_report=qc_report,
            cost=0.0,
        )

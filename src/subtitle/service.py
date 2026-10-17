"""High-level Subtitle & Transcription Service coordinating ASR, Translation, Validation, and Caching."""

import logging
from pathlib import Path
from typing import Optional, Tuple

from src.subtitle.adapters.base_asr import BaseASRAdapter
from src.subtitle.adapters.base_translator import BaseTranslationAdapter
from src.subtitle.adapters.glossary_translator import GlossaryTranslationAdapter
from src.subtitle.adapters.mock_asr import MockASRAdapter
from src.subtitle.cache import SubtitleCache
from src.subtitle.demuxer import AudioDemuxer, compute_file_sha256
from src.subtitle.models import SubtitleDocument, SubtitleValidationReport
from src.subtitle.srt_engine import SRTEngine

logger = logging.getLogger(__name__)


class SubtitleService:
    """Service orchestrating audio demuxing, Chinese ASR, Vietnamese translation, and SRT export."""

    def __init__(
        self,
        asr_adapter: Optional[BaseASRAdapter] = None,
        translation_adapter: Optional[BaseTranslationAdapter] = None,
        demuxer: Optional[AudioDemuxer] = None,
        cache: Optional[SubtitleCache] = None,
    ):
        self.asr = asr_adapter or MockASRAdapter()
        self.translator = translation_adapter or GlossaryTranslationAdapter()
        self.demuxer = demuxer or AudioDemuxer()
        self.cache = cache or SubtitleCache()
        self.srt_engine = SRTEngine()

    def process_audio(
        self,
        audio_path: Path,
        item_id: str,
        dedup_key: str,
        force_recompute: bool = False,
    ) -> Tuple[SubtitleDocument, SubtitleValidationReport, str]:
        """Process an audio file through ASR, translation, validation, and SRT generation."""
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        audio_hash = compute_file_sha256(audio_path)
        cache_key = self.cache.generate_cache_key(
            audio_hash=audio_hash,
            asr_model=self.asr.model_name,
            trans_model=self.translator.model_name,
        )

        # 1. Check Cache
        if not force_recompute:
            cached_doc = self.cache.get(cache_key)
            if cached_doc:
                logger.info(f"Returning cached subtitle document for item {item_id}")
                report = self.srt_engine.validate_subtitles(cached_doc.segments)
                srt_str = self.srt_engine.export_srt(cached_doc.segments)
                return cached_doc, report, srt_str

        # 2. Transcribe Chinese Speech
        logger.info(f"Transcribing Chinese audio using {self.asr.model_name}...")
        transcript_segments = self.asr.transcribe(audio_path)

        # 3. Translate to Vietnamese
        logger.info(f"Translating to Vietnamese using {self.translator.model_name}...")
        subtitle_segments = self.translator.translate_segments(transcript_segments)

        # 4. Validate Quality
        report = self.srt_engine.validate_subtitles(subtitle_segments)

        # 5. Build SubtitleDocument
        doc = SubtitleDocument(
            item_id=item_id,
            dedup_key=dedup_key,
            audio_hash=audio_hash,
            asr_model=self.asr.model_name,
            translation_model=self.translator.model_name,
            segments=subtitle_segments,
        )

        # 6. Save to Cache
        self.cache.put(cache_key, doc)

        # 7. Generate SRT
        srt_str = self.srt_engine.export_srt(subtitle_segments)
        return doc, report, srt_str

    def process_video(
        self,
        video_path: Path,
        item_id: str,
        dedup_key: str,
        force_recompute: bool = False,
    ) -> Tuple[SubtitleDocument, SubtitleValidationReport, str]:
        """Demux audio from video and process transcription & translation."""
        wav_path = self.demuxer.extract_audio(video_path=video_path)
        return self.process_audio(
            audio_path=wav_path,
            item_id=item_id,
            dedup_key=dedup_key,
            force_recompute=force_recompute,
        )

    def edit_subtitle_text(
        self,
        document: SubtitleDocument,
        segment_index: int,
        new_text_vi: str,
    ) -> Tuple[SubtitleDocument, SubtitleValidationReport, str]:
        """Edit translated Vietnamese text of a segment and revalidate."""
        updated_doc = self.srt_engine.edit_segment(
            doc=document,
            index=segment_index,
            new_text_vi=new_text_vi,
        )
        report = self.srt_engine.validate_subtitles(updated_doc.segments)
        srt_str = self.srt_engine.export_srt(updated_doc.segments)
        return updated_doc, report, srt_str

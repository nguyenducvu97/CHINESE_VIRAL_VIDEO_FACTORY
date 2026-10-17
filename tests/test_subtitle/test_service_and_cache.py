"""Unit tests for SubtitleService pipeline, caching, and editing."""

import pytest
from pathlib import Path
from src.subtitle.adapters.glossary_translator import GlossaryTranslationAdapter
from src.subtitle.adapters.mock_asr import MockASRAdapter
from src.subtitle.cache import SubtitleCache
from src.subtitle.service import SubtitleService


@pytest.fixture
def dummy_audio_file(tmp_path: Path) -> Path:
    """Create a temporary dummy audio file to generate deterministic hash."""
    audio_file = tmp_path / "test_audio.wav"
    audio_file.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    return audio_file


def test_subtitle_service_pipeline_and_cache(tmp_path: Path, dummy_audio_file: Path):
    """Verify transcription, translation, and cache reuse on subsequent calls."""
    cache_dir = tmp_path / "cache"
    cache = SubtitleCache(cache_dir=cache_dir)
    service = SubtitleService(
        asr_adapter=MockASRAdapter(),
        translation_adapter=GlossaryTranslationAdapter(),
        cache=cache,
    )

    # First Run: processes and caches
    doc1, report1, srt1 = service.process_audio(
        audio_path=dummy_audio_file,
        item_id="item_101",
        dedup_key="bilibili:BV_SAMPLE_101",
    )

    assert report1.is_valid is True
    assert len(doc1.segments) == 3
    assert "00:00:00,500 --> 00:00:03,500" in srt1

    # Check cache file exists on disk
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 1

    # Second Run: hits cache without recomputing
    doc2, report2, srt2 = service.process_audio(
        audio_path=dummy_audio_file,
        item_id="item_101",
        dedup_key="bilibili:BV_SAMPLE_101",
    )

    assert doc2.audio_hash == doc1.audio_hash
    assert len(doc2.segments) == len(doc1.segments)
    assert srt2 == srt1


def test_subtitle_service_editing(tmp_path: Path, dummy_audio_file: Path):
    """Verify editing a subtitle segment updates the document and re-generates SRT."""
    service = SubtitleService(cache=SubtitleCache(cache_dir=tmp_path / "cache"))

    doc, _, _ = service.process_audio(
        audio_path=dummy_audio_file,
        item_id="item_102",
        dedup_key="bilibili:BV_SAMPLE_102",
    )

    # Edit segment 1
    new_text = "Chào mọi người, ván trượt bay đã hoàn thành!"
    updated_doc, report, new_srt = service.edit_subtitle_text(
        document=doc,
        segment_index=1,
        new_text_vi=new_text,
    )

    assert updated_doc.segments[0].text_vi == new_text
    assert new_text in new_srt
    assert report.is_valid is True

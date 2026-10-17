"""Unit tests for GlossaryTranslationAdapter."""

import pytest
from src.subtitle.adapters.glossary_translator import GlossaryTranslationAdapter
from src.subtitle.models import TranscriptSegment


def test_translate_text_with_technical_glossary():
    """Verify phrase replacement preserves technical context and cleans spaces."""
    adapter = GlossaryTranslationAdapter()
    zh_text = "大家看，这块会飞的滑板动力来自于底部四个涵道无刷电机！"
    vi_text = adapter.translate_text(zh_text)

    assert "Mọi người nhìn xem," in vi_text
    assert "chiếc ván trượt biết bay" in vi_text
    assert "động cơ không chổi than" in vi_text


def test_translate_segments_maintains_timing():
    """Verify segment translation preserves exact start and end timestamps."""
    adapter = GlossaryTranslationAdapter()
    segments = [
        TranscriptSegment(index=1, start_ms=500, end_ms=3000, text_zh="大家好，今天我们来进行测试！"),
        TranscriptSegment(index=2, start_ms=3200, end_ms=6500, text_zh="现在马上进行第一次飞行测试。"),
    ]

    subs = adapter.translate_segments(segments)
    assert len(subs) == 2
    assert subs[0].start_ms == 500
    assert subs[0].end_ms == 3000
    assert len(subs[0].text_vi) > 0
    assert subs[1].start_ms == 3200
    assert subs[1].end_ms == 6500

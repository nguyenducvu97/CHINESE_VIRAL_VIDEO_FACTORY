"""Glossary-aware and Rule-based Chinese to Vietnamese Translation Adapter."""

import logging
from typing import Dict, List, Optional

from src.subtitle.adapters.base_translator import BaseTranslationAdapter
from src.subtitle.models import SubtitleSegment, TranscriptSegment

logger = logging.getLogger(__name__)

# Standard context glossary for viral video domains (Tech, Comedy, Drama, Daily Life)
DEFAULT_GLOSSARY: Dict[str, str] = {
    # Pronouns & Openers
    "大家看": "Mọi người nhìn xem,",
    "大家好": "Xin chào mọi người,",
    "今天": "hôm nay",
    "终于": "cuối cùng cũng",
    "现在": "bây giờ",
    "马上": "ngay lập tức",
    "我们": "chúng ta",
    "我": "tôi",
    # Verbs & Phrases
    "做出来了": "chế tạo xong rồi!",
    "试飞成功": "thử nghiệm bay thành công!",
    "来进行": "tiến hành",
    "进行": "thực hiện",
    "第一次": "lần đầu tiên",
    "测试": "kiểm tra",
    "悬停": "bay lơ lửng",
    "穿越": "xuyên không",
    "古代": "thời cổ đại",
    "治病": "chữa bệnh",
    # Technical & DIY terms
    "会飞的滑板": "chiếc ván trượt biết bay",
    "飞行滑板": "ván trượt bay",
    "滑板": "ván trượt",
    "动力来自于": "động lực đến từ",
    "底部": "phía đáy",
    "高转速": "tốc độ cao",
    "涵道无刷电机": "động cơ không chổi than ống dẫn",
    "无刷电机": "động cơ không chổi than",
    "涵道风扇": "quạt ống dẫn",
    "程序员": "lập trình viên",
    "御医": "ngự y",
    "代码": "dòng mã",
    "打铁花": "đập hoa sắt",
    "非遗": "di sản phi vật thể",
    "流星": "sao băng",
}


class GlossaryTranslationAdapter(BaseTranslationAdapter):
    """Translates Chinese phrases into natural Vietnamese using contextual glossaries."""

    def __init__(
        self,
        model_name: str = "local-glossary-v1",
        custom_glossary: Optional[Dict[str, str]] = None,
    ):
        super().__init__(model_name=model_name)
        self.glossary = {**DEFAULT_GLOSSARY, **(custom_glossary or {})}
        # Sort keys by length descending to match longest phrases first
        self._sorted_keys = sorted(self.glossary.keys(), key=len, reverse=True)

    def translate_text(self, text_zh: str) -> str:
        """Translate a single Chinese sentence into Vietnamese."""
        if not text_zh.strip():
            return ""

        translated = text_zh
        for zh_term in self._sorted_keys:
            if zh_term in translated:
                vi_term = self.glossary[zh_term]
                translated = translated.replace(zh_term, f" {vi_term} ")

        # Clean multiple spaces and normalize punctuation
        cleaned = " ".join(translated.split())
        # Capitalize first letter
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]
        return cleaned

    def translate_segments(
        self, segments: List[TranscriptSegment]
    ) -> List[SubtitleSegment]:
        """Translate all segments maintaining exact millisecond timestamps."""
        subtitles: List[SubtitleSegment] = []
        for seg in segments:
            text_vi = self.translate_text(seg.text_zh)
            subtitles.append(
                SubtitleSegment(
                    index=seg.index,
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms,
                    text_zh=seg.text_zh,
                    text_vi=text_vi,
                    speaker=seg.speaker,
                )
            )
        return subtitles

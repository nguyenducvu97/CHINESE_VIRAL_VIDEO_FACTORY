"""Abstract Base Class for Chinese to Vietnamese Translation."""

from abc import ABC, abstractmethod
from typing import List

from src.subtitle.models import SubtitleSegment, TranscriptSegment


class BaseTranslationAdapter(ABC):
    """Abstract interface for translation adapters."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def translate_segments(
        self, segments: List[TranscriptSegment]
    ) -> List[SubtitleSegment]:
        """Translate a list of Chinese transcript segments into natural Vietnamese.
        
        Args:
            segments: List of TranscriptSegment from ASR.
            
        Returns:
            List of SubtitleSegment with both text_zh and text_vi.
        """
        pass

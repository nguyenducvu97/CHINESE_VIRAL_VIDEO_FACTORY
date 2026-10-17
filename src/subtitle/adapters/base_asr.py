"""Abstract Base Class for Chinese Automatic Speech Recognition (ASR)."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from src.subtitle.models import TranscriptSegment


class BaseASRAdapter(ABC):
    """Abstract interface for speech-to-text adapters."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def transcribe(self, audio_path: Path) -> List[TranscriptSegment]:
        """Transcribe Chinese audio file into timestamped segments.
        
        Args:
            audio_path: Path to 16kHz WAV audio.
            
        Returns:
            List of TranscriptSegment objects with start_ms, end_ms, and text_zh.
        """
        pass

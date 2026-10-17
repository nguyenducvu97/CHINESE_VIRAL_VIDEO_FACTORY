"""Abstract Base Class for Vietnamese Text-to-Speech (TTS)."""

from abc import ABC, abstractmethod
from pathlib import Path

from src.dubbing.models import VoiceProfile


class BaseTTSAdapter(ABC):
    """Abstract interface for speech synthesis adapters."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: VoiceProfile,
        output_path: Path,
    ) -> Path:
        """Synthesize text into a WAV audio file.
        
        Args:
            text: Text to synthesize.
            voice: Voice profile configuration.
            output_path: Target WAV file location.
            
        Returns:
            Path to generated audio file.
        """
        pass

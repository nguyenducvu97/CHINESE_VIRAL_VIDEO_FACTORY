"""Deterministic Mock ASR Adapter for testing and validation."""

from pathlib import Path
from typing import List, Optional

from src.subtitle.adapters.base_asr import BaseASRAdapter
from src.subtitle.models import TranscriptSegment

DEFAULT_SAMPLE_SEGMENTS = [
    TranscriptSegment(
        index=1,
        start_ms=500,
        end_ms=3500,
        text_zh="大家看，我今天终于把这块会飞的滑板给做出来了！",
        speaker="Speaker_1",
        confidence=0.98,
    ),
    TranscriptSegment(
        index=2,
        start_ms=3800,
        end_ms=7200,
        text_zh="它的动力来自于底部四个高转速涵道无刷电机。",
        speaker="Speaker_1",
        confidence=0.95,
    ),
    TranscriptSegment(
        index=3,
        start_ms=7500,
        end_ms=11000,
        text_zh="现在我们马上进行第一次野外悬停与飞行测试！",
        speaker="Speaker_1",
        confidence=0.96,
    ),
]


class MockASRAdapter(BaseASRAdapter):
    """Mock ASR adapter returning deterministic segments for reliable testing."""

    def __init__(self, model_name: str = "mock-whisper-zh", fixture_segments: Optional[List[TranscriptSegment]] = None):
        super().__init__(model_name=model_name)
        self.fixture_segments = fixture_segments or DEFAULT_SAMPLE_SEGMENTS

    def transcribe(self, audio_path: Path) -> List[TranscriptSegment]:
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        return self.fixture_segments

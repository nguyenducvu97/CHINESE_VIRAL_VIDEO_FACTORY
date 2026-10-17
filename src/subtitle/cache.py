"""Persistent Cache for Transcription and Translation results."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from src.subtitle.models import SubtitleDocument

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "subtitles"


class SubtitleCache:
    """Manages disk-based cache for transcription and subtitle documents."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def generate_cache_key(audio_hash: str, asr_model: str, trans_model: str) -> str:
        """Generate deterministic cache key based on audio hash and model identifiers."""
        raw = f"{audio_hash.strip().lower()}:{asr_model.strip().lower()}:{trans_model.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[SubtitleDocument]:
        """Retrieve cached SubtitleDocument if available."""
        target_file = self.cache_dir / f"{cache_key}.json"
        if not target_file.exists():
            return None

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                doc = SubtitleDocument(**data)
                logger.info(f"Subtitle cache hit: {cache_key}")
                return doc
        except Exception as e:
            logger.warning(f"Failed to read cached subtitle file {target_file}: {e}")
            return None

    def put(self, cache_key: str, doc: SubtitleDocument) -> None:
        """Store SubtitleDocument in cache."""
        target_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(doc.model_dump(), f, ensure_ascii=False, indent=2)
            logger.info(f"Saved subtitle cache: {cache_key}")
        except Exception as e:
            logger.error(f"Failed to write to subtitle cache {target_file}: {e}")

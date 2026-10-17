"""CLI Script to execute Transcription & Vietsub generation for CVVF."""

import argparse
import logging
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.subtitle.adapters.glossary_translator import GlossaryTranslationAdapter
from src.subtitle.adapters.mock_asr import MockASRAdapter
from src.subtitle.cache import SubtitleCache
from src.subtitle.service import SubtitleService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cvvf.subtitle")


def main():
    parser = argparse.ArgumentParser(description="Run Video Transcription & Subtitle Generation")
    parser.add_argument("--item-id", default="item_demo_01", help="Video item identifier")
    parser.add_argument("--dedup-key", default="bilibili:BV1KiJk67EQ9", help="Canonical video dedup key")
    parser.add_argument("--audio-path", default=None, help="Path to input audio file")
    parser.add_argument("--output-srt", default="data/output/sample_vietsub.srt", help="Output SRT file path")
    args = parser.parse_args()

    # Create dummy audio if none provided
    audio_path = Path(args.audio_path) if args.audio_path else Path("fixtures/audio/sample_chinese_audio.wav")
    if not audio_path.exists():
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        # Create minimal 16kHz PCM WAV header
        audio_path.write_bytes(
            b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        )
        logger.info(f"Created sample audio fixture at: {audio_path}")

    service = SubtitleService(
        asr_adapter=MockASRAdapter(model_name="whisper-base-zh"),
        translation_adapter=GlossaryTranslationAdapter(model_name="contextual-glossary-vi"),
        cache=SubtitleCache(cache_dir=Path("data/cache/subtitles")),
    )

    doc, report, srt_content = service.process_audio(
        audio_path=audio_path,
        item_id=args.item_id,
        dedup_key=args.dedup_key,
    )

    print("\n" + "=" * 70)
    print("SUBTITLE TRANSCRIPTION & TRANSLATION REPORT")
    print("=" * 70)
    print(f"Item ID:             {doc.item_id}")
    print(f"Dedup Key:           {doc.dedup_key}")
    print(f"Audio SHA-256:       {doc.audio_hash[:16]}...")
    print(f"ASR Model:           {doc.asr_model}")
    print(f"Translation Model:   {doc.translation_model}")
    print(f"Total Segments:      {len(doc.segments)}")
    print(f"Validation Status:   {'PASSED' if report.is_valid else 'FAILED'} (Errors: {report.errors_count}, Warnings: {report.warnings_count})")
    print("\nGENERATED SRT CONTENT:")
    print("-" * 50)
    print(srt_content.strip())
    print("-" * 50)

    # Save SRT to disk
    out_srt_path = Path(args.output_srt)
    out_srt_path.parent.mkdir(parents=True, exist_ok=True)
    out_srt_path.write_text(srt_content, encoding="utf-8")
    print(f"Saved SRT file to: {out_srt_path}\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()

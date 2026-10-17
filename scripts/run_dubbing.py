"""CLI Script to execute Vietnamese Dubbing workflow for CVVF."""

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

from src.dubbing.adapters.mock_tts import MockTTSAdapter
from src.dubbing.adapters.edge_tts_adapter import EdgeTTSAdapter
from src.dubbing.models import VoiceGender, VoiceProfile
from src.dubbing.service import DubbingService
from src.subtitle.adapters.glossary_translator import GlossaryTranslationAdapter
from src.subtitle.adapters.mock_asr import MockASRAdapter
from src.subtitle.cache import SubtitleCache
from src.subtitle.service import SubtitleService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cvvf.dubbing")


def main():
    parser = argparse.ArgumentParser(description="Run Vietnamese Dubbing for Subtitled Video")
    parser.add_argument("--item-id", default="item_demo_01", help="Video item identifier")
    parser.add_argument("--dedup-key", default="bilibili:BV1KiJk67EQ9", help="Canonical video dedup key")
    parser.add_argument("--use-edge-tts", action="store_true", help="Use live EdgeTTS neural voice instead of mock")
    parser.add_argument("--output-dir", default="data/output/dubbing", help="Output directory for audio tracks")
    args = parser.parse_args()

    audio_path = Path("fixtures/audio/sample_chinese_audio.wav")
    if not audio_path.exists():
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(
            b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        )

    # 1. Obtain Subtitle Document via SubtitleService
    sub_service = SubtitleService(
        asr_adapter=MockASRAdapter(model_name="whisper-base-zh"),
        translation_adapter=GlossaryTranslationAdapter(model_name="contextual-glossary-vi"),
        cache=SubtitleCache(cache_dir=Path("data/cache/subtitles")),
    )
    doc, _, _ = sub_service.process_audio(audio_path=audio_path, item_id=args.item_id, dedup_key=args.dedup_key)

    # 2. Select Voice and TTS Adapter
    if args.use_edge_tts:
        tts_adapter = EdgeTTSAdapter()
        voice = VoiceProfile(
            voice_id="vi-VN-HoaiMyNeural",
            gender=VoiceGender.FEMALE,
            display_name="Hoài My Neural (Microsoft Edge)",
            provider="edge-tts",
        )
    else:
        tts_adapter = MockTTSAdapter()
        voice = VoiceProfile(
            voice_id="mock-female-fast",
            gender=VoiceGender.FEMALE,
            display_name="Mock Voice Female",
            provider="mock-tts",
        )

    dub_service = DubbingService(
        tts_adapter=tts_adapter,
        cache_dir=Path("data/cache/tts"),
    )

    out_dir = Path(args.output_dir)
    result = dub_service.dub_video(
        subtitle_doc=doc,
        original_audio_path=audio_path,
        output_dir=out_dir,
        voice_profile=voice,
        total_duration_ms=12000,
    )

    print("\n" + "=" * 70)
    print("VIETNAMESE DUBBING & AUDIO QC REPORT")
    print("=" * 70)
    print(f"Item ID:               {result.item_id}")
    print(f"Dedup Key:             {result.dedup_key}")
    print(f"Voice Profile:         {result.voice_profile.display_name} ({result.voice_profile.voice_id})")
    print(f"Total Segments Dubbed: {len(result.segments)}")
    print(f"Mixed Audio Output:    {result.mixed_audio_path}")
    print(f"QC Status:             {'PASSED' if result.qc_report.is_passed else 'FAILED'}")
    print(f"Duration Drift:        {result.qc_report.drift_ms}ms")
    print(f"Clipping Detected:     {'YES (Warning)' if result.qc_report.is_clipping else 'No'}")
    print(f"Silence Detected:      {'YES (Warning)' if result.qc_report.is_silent else 'No'}")
    print(f"Cost Impact:           ${result.cost:.2f}")

    if result.qc_report.limitations:
        print("\nTECHNICAL LIMITATIONS (TRANSPARENCY):")
        for lim in result.qc_report.limitations:
            print(f"  * {lim}")

    print("\nDUBBED SEGMENTS SUMMARY:")
    for seg in result.segments:
        print(f"  [{seg.index}] {seg.start_ms}ms -> {seg.end_ms}ms (Target: {seg.target_duration_ms}ms, Tempo: {seg.tempo_factor:.2f}x)")
        print(f"      Text: {seg.text_vi}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

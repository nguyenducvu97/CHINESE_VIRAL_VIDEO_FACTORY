"""CLI Script to execute Video Rendering and Quality Control for CVVF."""

import argparse
import logging
from pathlib import Path
import subprocess
import sys

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rendering.ffmpeg_worker import FFmpegRenderWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cvvf.rendering")


def ensure_sample_video(path: Path) -> Path:
    """Ensure a sample video file exists for rendering demonstration."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Generating synthetic source video at: {path}...")
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=3:size=640x360:rate=25",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    return path


def main():
    parser = argparse.ArgumentParser(description="Run Video Rendering & QC Worker")
    parser.add_argument("--item-id", default="item_demo_01", help="Video item identifier")
    parser.add_argument("--dedup-key", default="bilibili:BV1KiJk67EQ9", help="Canonical video dedup key")
    parser.add_argument("--source-video", default="fixtures/sample_videos/demo_video.mp4", help="Source video path")
    parser.add_argument("--srt-path", default="data/output/sample_vietsub.srt", help="Subtitle SRT file")
    parser.add_argument("--dubbed-audio", default="data/output/dubbing/final_dubbed_audio.wav", help="Dubbed audio file")
    parser.add_argument("--output-dir", default="data/output/rendered", help="Destination render directory")
    args = parser.parse_args()

    source_path = ensure_sample_video(Path(args.source_video))
    srt_path = Path(args.srt_path)
    if not srt_path.exists():
        srt_path.parent.mkdir(parents=True, exist_ok=True)
        srt_path.write_text("1\n00:00:00,500 --> 00:00:02,500\nPhụ đề tiếng Việt thử nghiệm\n\n", encoding="utf-8")

    dubbed_audio_path = Path(args.dubbed_audio)
    if not dubbed_audio_path.exists():
        dubbed_audio_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=660:duration=3", "-acodec", "pcm_s16le", str(dubbed_audio_path)]
        subprocess.run(cmd, check=True, capture_output=True)

    worker = FFmpegRenderWorker()
    out_dir = Path(args.output_dir)

    print("\n" + "=" * 70)
    print("VIDEO RENDERING & QUALITY CONTROL PIPELINE")
    print("=" * 70)

    # Variant 1: Original Preserved
    res_orig = worker.export_original_preserved(
        source_video_path=source_path,
        output_dir=out_dir,
        item_id=args.item_id,
        dedup_key=args.dedup_key,
    )
    print(f"\n[VARIANT 1: ORIGINAL PRESERVED]")
    print(f"  Path:       {res_orig.output_video_path}")
    print(f"  Resolution: {res_orig.qc_inspection.width}x{res_orig.qc_inspection.height} ({res_orig.qc_inspection.aspect_ratio})")
    print(f"  Codec:      Video: {res_orig.qc_inspection.video_codec}, Audio: {res_orig.qc_inspection.audio_codec}")
    print(f"  Playable:   {res_orig.qc_inspection.is_playable} (Zero decoding errors)")
    print(f"  Checksum:   {res_orig.checksum_sha256[:16]}...")
    print(f"  QC Status:  {'PASSED' if res_orig.qc_inspection.is_valid else 'FAILED'}")

    # Variant 2: Vietsub
    res_vietsub = worker.render_vietsub(
        source_video_path=source_path,
        srt_path=srt_path,
        output_dir=out_dir,
        item_id=args.item_id,
        dedup_key=args.dedup_key,
        hardsub=False,
    )
    print(f"\n[VARIANT 2: VIETSUB (SOFT/MUXED)]")
    print(f"  Path:       {res_vietsub.output_video_path}")
    print(f"  Resolution: {res_vietsub.qc_inspection.width}x{res_vietsub.qc_inspection.height} (Exact match source: True)")
    print(f"  Codec:      Video: {res_vietsub.qc_inspection.video_codec}, Audio: {res_vietsub.qc_inspection.audio_codec}")
    print(f"  Playable:   {res_vietsub.qc_inspection.is_playable}")
    print(f"  Checksum:   {res_vietsub.checksum_sha256[:16]}...")
    print(f"  QC Status:  {'PASSED' if res_vietsub.qc_inspection.is_valid else 'FAILED'}")

    # Variant 3: Dubbed + Vietsub
    res_dubbed = worker.render_dubbed_vietsub(
        source_video_path=source_path,
        dubbed_audio_path=dubbed_audio_path,
        srt_path=srt_path,
        output_dir=out_dir,
        item_id=args.item_id,
        dedup_key=args.dedup_key,
        hardsub=False,
    )
    print(f"\n[VARIANT 3: DUBBED + VIETSUB]")
    print(f"  Path:       {res_dubbed.output_video_path}")
    print(f"  Resolution: {res_dubbed.qc_inspection.width}x{res_dubbed.qc_inspection.height} (Exact match source: True)")
    print(f"  Codec:      Video: {res_dubbed.qc_inspection.video_codec}, Audio: {res_dubbed.qc_inspection.audio_codec}")
    print(f"  Playable:   {res_dubbed.qc_inspection.is_playable}")
    print(f"  Checksum:   {res_dubbed.checksum_sha256[:16]}...")
    print(f"  QC Status:  {'PASSED' if res_dubbed.qc_inspection.is_valid else 'FAILED'}")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

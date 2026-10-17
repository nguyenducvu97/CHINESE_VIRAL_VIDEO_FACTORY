"""CLI Script to execute Classification & Viral Scoring for CVVF."""

import argparse
import json
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

from src.core.models import StandardVideoItem
from src.discovery.dedup import DeduplicationStore
from src.scoring.viral_scorer import ViralScorer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cvvf.scoring")


def main():
    parser = argparse.ArgumentParser(description="Run Video Classification & Viral Scoring")
    parser.add_argument("--storage", default="data/discovered_videos.json", help="Path to stored discovered videos")
    parser.add_argument("--output", default="data/scored_videos.json", help="Path to output scored videos")
    args = parser.parse_args()

    storage_path = Path(args.storage)
    if not storage_path.exists():
        logger.error(f"Storage file {storage_path} not found. Please run discovery first.")
        return

    store = DeduplicationStore(storage_path=storage_path)
    items = store.get_all()
    logger.info(f"Loaded {len(items)} videos from storage for scoring.")

    scorer = ViralScorer()
    scored_items = []

    print("\n" + "=" * 70)
    print("CLASSIFICATION & VIRAL SCORING REPORT")
    print("=" * 70)

    for idx, item in enumerate(items, 1):
        scored = scorer.score_video(item)
        scored_items.append(scored.model_dump())

        print(f"\n[{idx}] {item.title}")
        print(f"    Canonical URL:            {item.canonical_url}")
        print(f"    Category:                 {scored.category.value} (Confidence: {scored.category_confidence:.0%})")
        print(f"    Measured Viral Score:     {scored.measured_viral_score}/100" if scored.measured_viral_score else "    Measured Viral Score:     None (INSUFFICIENT_DATA)")
        print(f"    Inferred Potential Score: {scored.inferred_potential_score}/100" if scored.inferred_potential_score else "    Inferred Potential Score: None")
        print(f"    Confidence Level:         {scored.confidence_level.value}")
        print(f"    Review Status:            {scored.status.value}")
        print(f"    Explanations:")
        for exp in scored.scoring_explanation:
            print(f"      - {exp}")

    print("=" * 70 + "\n")

    # Persist scored items
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(scored_items, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(scored_items)} scored records to {out_path}")


if __name__ == "__main__":
    main()

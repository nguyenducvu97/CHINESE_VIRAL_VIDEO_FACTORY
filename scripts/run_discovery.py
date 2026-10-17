"""CLI Script to execute Discovery MVP for CVVF."""

import argparse
import json
import logging
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.discovery.adapters.bilibili_adapter import BilibiliDiscoveryAdapter
from src.discovery.service import DiscoveryService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cvvf.discovery")


def main():
    parser = argparse.ArgumentParser(description="Run Chinese Viral Video Discovery MVP")
    parser.add_argument("--platform", default="bilibili", help="Platform adapter to query")
    parser.add_argument("--page", type=int, default=1, help="Page number (1-based)")
    parser.add_argument("--page-size", type=int, default=5, help="Number of items to fetch")
    parser.add_argument("--dry-run", action="store_true", help="Run with fixture data instead of live network")
    parser.add_argument("--storage", default="data/discovered_videos.json", help="Path to persistence JSON file")
    args = parser.parse_args()

    storage_path = Path(args.storage)
    service = DiscoveryService(storage_path=storage_path)

    # Register Bilibili adapter
    bilibili = BilibiliDiscoveryAdapter()
    service.register_adapter(bilibili)

    logger.info(
        f"Starting discovery run: platform={args.platform}, page={args.page}, "
        f"page_size={args.page_size}, dry_run={args.dry_run}"
    )

    result = service.discover_trending(
        platform_name=args.platform,
        page=args.page,
        page_size=args.page_size,
        dry_run=args.dry_run,
    )

    print("\n" + "=" * 60)
    print("DISCOVERY AUDIT REPORT")
    print("=" * 60)
    print(f"Timestamp:           {result.run_timestamp}")
    print(f"Platform:            {result.platform}")
    print(f"Total Fetched:       {result.total_fetched}")
    print(f"New Unique Added:    {result.new_unique_added}")
    print(f"Duplicates Filtered: {result.duplicates_filtered}")
    print(f"Total Stored Now:    {len(service.list_all_stored())}")
    print(f"Errors:              {len(result.errors)}")

    if result.items:
        print("\nSAMPLE DISCOVERED ITEMS:")
        for idx, item in enumerate(result.items[:3], 1):
            print(f"\n[{idx}] {item.title}")
            print(f"    Platform ID:    {item.source_item_id}")
            print(f"    Canonical URL:  {item.canonical_url}")
            print(f"    Author:         {item.author.name} (ID: {item.author.id})")
            print(f"    Views:          {item.metrics.views:,}")
            print(f"    Likes:          {item.metrics.likes:,}")
            print(f"    Shares:         {item.metrics.shares or 0:,}")
            print(f"    Comments:       {item.metrics.comments or 0:,}")
            print(f"    Rights Status:  {item.rights_status.value}")
            print(f"    Missing Fields: {', '.join(item.missing_fields) if item.missing_fields else 'None'}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

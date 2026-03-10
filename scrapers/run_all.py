"""Orchestrator that runs every scraper and merges the results.

Usage:
    python -m scrapers.run_all
"""
import json
import logging
import os
import shutil
from datetime import datetime

from scrapers.iit_delhi import IITDelhiScraper
from scrapers.iit_madras import IITMadrasScraper
from scrapers.iit_bombay import IITBombayScraper
from scrapers.iit_kharagpur import IITKharagpurScraper
from scrapers.iit_kanpur import IITKanpurScraper
from scrapers.iiser_pune import IISERPuneScraper
from scrapers.generic_scraper import scrape_all_generic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DEDICATED_SCRAPERS = [
    IITDelhiScraper,
    IITMadrasScraper,
    IITBombayScraper,
    IITKharagpurScraper,
    IITKanpurScraper,
    IISERPuneScraper,
]


def deduplicate(openings):
    """Remove duplicate records based on their hash."""
    seen = set()
    unique = []
    for item in openings:
        h = item.get("hash", "")
        if h and h not in seen:
            seen.add(h)
            unique.append(item)
    return unique


def run_all():
    """Execute all scrapers and save a merged, deduplicated JSON file."""
    all_openings = []

    for scraper_cls in DEDICATED_SCRAPERS:
        scraper = scraper_cls()
        try:
            results = scraper.scrape()
            all_openings.extend(results)
            logger.info(
                "%s returned %d openings.", scraper.institute_name, len(results)
            )
        except Exception as exc:
            logger.error("Scraper %s failed: %s", scraper_cls.__name__, exc)

    try:
        generic_results = scrape_all_generic()
        all_openings.extend(generic_results)
    except Exception as exc:
        logger.error("Generic scraper batch failed: %s", exc)

    all_openings = deduplicate(all_openings)
    logger.info("Total unique openings after dedup: %d", len(all_openings))

    merged_path = os.path.join(
        DATA_DIR,
        "all_openings_{}.json".format(datetime.now().strftime("%Y%m%d")),
    )
    try:
        with open(merged_path, "w", encoding="utf-8") as fh:
            json.dump(all_openings, fh, ensure_ascii=False, indent=2)
        logger.info("Merged file saved to %s", merged_path)

        # Also copy as the canonical latest snapshot (used by Streamlit Cloud)
        latest_path = os.path.join(DATA_DIR, "all_openings_latest.json")
        shutil.copy2(merged_path, latest_path)
        logger.info("Latest snapshot updated: %s", latest_path)
    except IOError as exc:
        logger.error("Failed to write merged file: %s", exc)

    return all_openings


if __name__ == "__main__":
    run_all()

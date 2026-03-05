import logging
import os
import re
import json
import hashlib
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler(),
    ],
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)


class BaseScraper(ABC):
    """Base class for all institute scrapers."""

    def __init__(self, institute_name, url, use_selenium=False):
        self.institute_name = institute_name
        self.url = url
        self.use_selenium = use_selenium
        self.logger = logging.getLogger(self.institute_name)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        self.driver = None

    def _init_selenium(self):
        """Initialize a headless Chrome WebDriver."""
        try:
            options = ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument(
                "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_page_load_timeout(30)
            self.logger.info("Selenium WebDriver initialized.")
        except Exception as exc:
            self.logger.warning("Failed to initialize WebDriver: %s", exc)
            self.logger.warning("Selenium unavailable, will fall back to requests.")
            self.driver = None
            raise

    def fetch_page(self, url=None, timeout=15):
        """Fetch page content using requests (static) or Selenium (dynamic).

        When use_selenium is True but Chrome is not installed the method
        automatically falls back to a plain requests fetch so the pipeline
        does not crash.
        """
        target_url = url or self.url
        if self.use_selenium:
            try:
                return self._fetch_with_selenium(target_url)
            except Exception:
                self.logger.warning(
                    "Selenium failed for %s, falling back to requests.",
                    target_url,
                )
                return self._fetch_with_requests(target_url, timeout)
        return self._fetch_with_requests(target_url, timeout)

    def _fetch_with_requests(self, url, timeout=15):
        """Fetch static HTML with requests."""
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            self.logger.info("Fetched %s (status %d)", url, response.status_code)
            return response.text
        except requests.exceptions.Timeout:
            self.logger.error("Timeout while fetching %s", url)
            return None
        except requests.exceptions.ConnectionError:
            self.logger.error("Connection error for %s", url)
            return None
        except requests.exceptions.HTTPError as exc:
            self.logger.error("HTTP error for %s: %s", url, exc)
            return None
        except requests.exceptions.RequestException as exc:
            self.logger.error("Request failed for %s: %s", url, exc)
            return None

    def _fetch_with_selenium(self, url):
        """Fetch dynamic page content with Selenium."""
        if self.driver is None:
            self._init_selenium()
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            page_source = self.driver.page_source
            self.logger.info("Fetched (Selenium) %s", url)
            return page_source
        except Exception as exc:
            self.logger.error("Selenium fetch failed for %s: %s", url, exc)
            return None

    @staticmethod
    def parse_html(html):
        """Parse raw HTML into a BeautifulSoup object."""
        if html is None:
            return None
        return BeautifulSoup(html, "lxml")

    @abstractmethod
    def scrape(self):
        """Scrape openings from the institute website.
        Must return a list of dicts with standardized keys.
        """

    @staticmethod
    def generate_hash(text):
        """Generate a SHA-256 hash for deduplication."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def save_to_json(self, data, filename=None):
        """Persist scraped data as a JSON file in the data directory."""
        if filename is None:
            safe_name = re.sub(r"[^a-zA-Z0-9]", "_", self.institute_name).lower()
            filename = f"{safe_name}_{datetime.now().strftime('%Y%m%d')}.json"
        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            self.logger.info("Saved %d records to %s", len(data), filepath)
        except IOError as exc:
            self.logger.error("Failed to save JSON: %s", exc)

    def cleanup(self):
        """Release resources."""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("WebDriver closed.")
            except Exception as exc:
                self.logger.error("Error closing WebDriver: %s", exc)


def clean_text(text):
    """Normalize whitespace and strip a string."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_dates(text):
    """Extract date-like strings from text.

    Handles formats:
      - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
      - YYYY-MM-DD
      - 12 Dec 2024 / 12th Dec 2024 / 12-Dec-2024
      - Dec 12, 2024 / December 12 2024
    Returns a list of matched date strings (may contain duplicates).
    """
    patterns = [
        # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
        r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b",
        # YYYY-MM-DD
        r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b",
        # 12th Dec 2024  /  12 Dec 2024  /  12-Dec-2024
        r"\b\d{1,2}(?:st|nd|rd|th)?[-/.\s]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/.\s]+\d{4}\b",
        # Dec 12, 2024  /  December 12 2024
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    ]
    dates = []
    for pattern in patterns:
        dates.extend(re.findall(pattern, text, re.IGNORECASE))
    return dates


def extract_department(text):
    """Try to extract a department name from raw_text.

    Looks for common patterns like:
      'Department of ...'  /  'Dept. of ...'  /  'School of ...'
    Returns the matched string or empty string.
    """
    patterns = [
        r"(?:Department|Dept\.?)\s+of\s+[A-Z][A-Za-z &/()-]{3,60}",
        r"School\s+of\s+[A-Z][A-Za-z &/()-]{3,50}",
        r"Centre\s+(?:for|of)\s+[A-Z][A-Za-z &/()-]{3,50}",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return clean_text(m.group(0))
    return ""


def extract_salary(text):
    """Extract salary/stipend amounts from text."""
    patterns = [
        r"Rs\.?\s*[\d,]+",
        r"INR\s*[\d,]+",
        r"[\d,]+\s*(?:per\s+month|p\.?m\.?|/-)",
    ]
    salaries = []
    for pattern in patterns:
        salaries.extend(re.findall(pattern, text, re.IGNORECASE))
    return salaries


def normalize_position_type(title):
    """Map a raw position title to a standard category."""
    title_lower = title.lower()
    mapping = {
        "jrf": ["junior research fellow", "jrf"],
        "srf": ["senior research fellow", "srf"],
        "project_associate": ["project associate", "project assistant"],
        "research_associate": ["research associate", "ra "],
        "research_assistant": ["research assistant"],
        "project_scientist": ["project scientist"],
        "project_engineer": ["project engineer"],
        "project_officer": ["project officer"],
        "post_doctoral": ["post doctoral", "postdoctoral", "post-doctoral", "pdf"],
    }
    for category, keywords in mapping.items():
        for keyword in keywords:
            if keyword in title_lower:
                return category
    return "other"

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

# Selenium imports – optional; scrapers fall back to requests when unavailable.
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

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


# Some institute sites have broken/self-signed TLS chains. For these hosts only,
# we disable certificate verification so scrapes don't fail completely.
# This is intentionally a tight allowlist.
_INSECURE_TLS_HOST_ALLOWLIST = {
    "www.isical.ac.in",
    "www.isid.ac.in",
    "isic.isichennai.res.in",
    "www.isine.ac.in",
    "jadavpuruniversity.in",
}


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
        """Initialize a headless Chrome WebDriver.

        If Selenium is not installed or Chrome / chromedriver is not
        available, logs a warning and raises so the caller can fall back
        to a plain requests fetch.
        """
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium package is not installed.")

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
        # Transient network issues are common for institute sites.
        # A small retry with backoff improves daily scrape stability without
        # significantly slowing down the pipeline.
        verify_tls = True
        try:
            from urllib.parse import urlparse

            host = urlparse(url).netloc.lower()
            if host in _INSECURE_TLS_HOST_ALLOWLIST:
                verify_tls = False
        except Exception:
            pass

        if not verify_tls:
            self.logger.warning(
                "TLS verification disabled for host in allowlist: %s",
                url,
            )

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=timeout, verify=verify_tls)
                response.raise_for_status()
                self.logger.info("Fetched %s (status %d)", url, response.status_code)
                return response.text
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                wait_s = 1.5 * (2 ** attempt)
                self.logger.warning(
                    "Network error fetching %s (attempt %d/3): %s; retrying in %.1fs",
                    url,
                    attempt + 1,
                    exc,
                    wait_s,
                )
                time.sleep(wait_s)
                continue
            except requests.exceptions.HTTPError as exc:
                self.logger.error("HTTP error for %s: %s", url, exc)
                return None
            except requests.exceptions.RequestException as exc:
                self.logger.error("Request failed for %s: %s", url, exc)
                return None

        self.logger.error("Failed to fetch %s after 3 attempts: %s", url, last_exc)
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
      - Walk-in-interview on 19.01.2026  (date extracted from surrounding text)
    Returns a list of matched date strings (may contain duplicates).
    """
    patterns = [
        # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
        r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b",
        # YYYY-MM-DD
        r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b",
        # 12th Dec 2024  /  12 Dec 2024  /  12-Dec-2024
        r"\b\d{1,2}(?:st|nd|rd|th)?[-/.\s]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/.\s]+\d{4}\b",
    # 12th December, 2024  /  12 December 2024
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,?\s+\d{4}\b",
        # Dec 12, 2024  /  December 12 2024
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    # Corrupted PDF/OCR format: DDMMYYYY (8 digits, e.g. "27032026")
    # Also handles DD1MM12026 (slashes OCR'd as "1"), e.g. "2710312026".
    # NOTE: We restrict the year to 2020-2027 to avoid spurious "2028"
    # matches that sometimes appear from broken PDF text extraction.
    r"(?<!\d)(\d{2})1?(\d{2})1?(202[0-7])(?!\d)",
    ]
    dates = []
    for i, pattern in enumerate(patterns):
        if i == len(patterns) - 1:
            # DDMMYYYY / DD1MM12026: reconstruct as DD/MM/YYYY
            for m in re.finditer(pattern, text, re.IGNORECASE):
                day, month, year = m.group(1), m.group(2), m.group(3)
                # Validate basic range
                if 1 <= int(day) <= 31 and 1 <= int(month) <= 12:
                    dates.append(f"{day}/{month}/{year}")
        else:
            dates.extend(re.findall(pattern, text, re.IGNORECASE))
    return dates


# Date formats tried when parsing a deadline string to a datetime object.
_DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%d/%m/%y",  "%d-%m-%y",  "%d.%m.%y",
    "%Y-%m-%d",  "%Y/%m/%d", "%Y.%m.%d",
    "%d %b %Y",  "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y",
    "%d %b. %Y",
    "%d %b %y",
]


def parse_deadline_date(deadline_str: str) -> Optional[datetime]:
    """Parse a raw deadline string into a datetime, or return None."""
    if not deadline_str or not deadline_str.strip():
        return None
    text = deadline_str.strip()
    # Normalize ordinal day suffixes: "18th March 2026" -> "18 March 2026"
    text = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)
    # Drop obvious notice numbers that look like dates: "2025-26/02".
    # IMPORTANT: don't reject real ISO dates like "2026-03-20".
    if re.fullmatch(r"\d{4}[-/]\d{2}[-/]\d{1,2}", text):
        parts = re.split(r"[-/]", text)
        if len(parts) == 3:
            y, mid, last = parts
            # Notice-number heuristic: middle part is a *2-digit year* (e.g. 26)
            # rather than a month (01-12).
            try:
                mid_i = int(mid)
            except ValueError:
                mid_i = 0
            if mid_i > 12:
                return None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            # Reject impossible day/month combinations that sometimes appear in
            # scraped PDFs (e.g. 31-11-2025). If strptime parsed it, it's real,
            # but most impossible combos won't parse anyway; keep this check as
            # a safety net if we later add more permissive parsing.
            if not (1 <= dt.month <= 12 and 1 <= dt.day <= 31):
                return None
            return dt
        except ValueError:
            continue
    # Flexible fallback via pandas (handles many edge cases)
    try:
        import pandas as pd
        ts = pd.Timestamp(text)
        return ts.to_pydatetime()
    except Exception:
        return None


def is_expired(deadline_str: str, today: Optional[datetime] = None) -> bool:
    """Return True only when the deadline is clearly in the past.

    Conservative rule:
      - If the date cannot be parsed → assume NOT expired (keep it).
      - If parsed date < today     → expired (hide it).
    """
    dt = parse_deadline_date(deadline_str)
    if dt is None:
        return False
    ref = today or datetime.now()
    return dt.date() < ref.date()


# URL patterns that are definitely not recruitment-specific detail pages.
# Fetching these would waste time and return wrong dates.
_JUNK_URL_FRAGMENTS = (
    "javascript:", "mailto:", "tel:", "google.com/forms", "docs.google",
    "forms.gle", "mathworks.com", "linkedin.com", "facebook.com",
)

# Filename keywords that indicate a PDF is NOT a recruitment advertisement —
# e.g. telephone directories, UG brochures, student conduct codes.  These are
# common attachment links found in site headers/footers on many institute pages
# and should not be treated as detail advertisement PDFs.
_JUNK_PDF_FILENAME_FRAGMENTS = (
    "telephone", "directory", "brochure", "conduct-code", "conduct_code",
    "discipline", "swagatham", "calendar", "timetable", "time-table",
    "fee-structure", "annual-report", "annual_report", "newsletter",
    "gazette", "nitc-calendar", "hostel", "rti-",
)

_JUNK_URL_PATHS = {
    "/", "/#", "",
}

# Keywords that appear near deadline text in recruitment notices.
_DEADLINE_KEYWORDS_RE = re.compile(
    r"(?:last\s+date|deadline|closing\s+date|last\s+date\s+of\s+application"
    r"|date\s+of\s+interview|walk.?in|application\s+last\s+date)",
    re.IGNORECASE,
)

# Phrases that frequently precede non-deadline dates inside advertisements
# (e.g. project tenure end dates). If a candidate date is near these phrases,
# we should ignore it.
_NON_DEADLINE_CONTEXT_RE = re.compile(
    r"(?:end\s+date|tenure\s+end|project\s+end|duration\s+of\s+the\s+project)",
    re.IGNORECASE,
)


def _is_junk_url(url: str) -> bool:
    """Return True if a detail URL is unlikely to hold a recruitment notice."""
    if not url or not url.startswith("http"):
        return True
    for frag in _JUNK_URL_FRAGMENTS:
        if frag in url:
            return True
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path.rstrip("/")
        if path in _JUNK_URL_PATHS:
            return True
        # Very short generic paths like /about, /home, /contact
        segments = [s for s in path.split("/") if s]
        if len(segments) == 1 and segments[0].lower() in (
            "about", "about-us", "home", "contact", "contact-us",
            "careers", "recruitment", "jobs", "vacancies",
            "how-reach", "reach-us", "news", "notices",
        ):
            return True
    except Exception:
        pass
    return False


def _extract_deadline_from_text(text: str) -> str:
    """Find the best deadline date in a block of text.

    Strategy:
      1. Search for a date that immediately follows a deadline-keyword phrase
         (e.g. "Last Date: 25/03/2026").  Return the first such hit.
      2. Fall back to the last date found anywhere in the text (common pattern:
         notices list dates top-to-bottom, last date = deadline).
    Returns an empty string when nothing parseable is found.
    """
    if not text:
        return ""

    # Some institutes include notice numbers like "2025-26/02" or "2024-25/11"
    # in prominent locations. Our date regex can misread these as dates.
    # If such a pattern occurs, it should never be used as a deadline.
    def _looks_like_notice_number(s: str) -> bool:
        s = (s or "").strip()
        # Examples: 2025-26/02, 2025-26/3, 2021-22/01
        return re.fullmatch(r"\d{4}[-/]\d{2}[-/]\d{1,2}", s) is not None
    for m in _DEADLINE_KEYWORDS_RE.finditer(text):
        # Look in the ~120 chars after the keyword for a date
        window = text[m.end(): m.end() + 120]
        candidates = extract_dates(window)
        for raw_date in candidates:
            # Ignore project end-date fields accidentally captured near keywords.
            # We look a bit around the candidate inside the window.
            try:
                pos = window.find(raw_date)
                around = window[max(0, pos - 40): pos + len(raw_date) + 40]
                if _NON_DEADLINE_CONTEXT_RE.search(around):
                    continue
            except Exception:
                pass
            if _looks_like_notice_number(raw_date):
                continue
            if parse_deadline_date(raw_date) is not None:
                return raw_date
    # Fallback: last parseable date anywhere in the text
    all_dates = extract_dates(text)
    for raw_date in reversed(all_dates):
        if _looks_like_notice_number(raw_date):
            continue
        if parse_deadline_date(raw_date) is not None:
            return raw_date
    return ""


def fetch_detail_deadline(url: str, session=None, timeout: int = 10) -> str:
    """Fetch a detail page (HTML or PDF) and extract a deadline date.

    Returns the best deadline string found, or "" if nothing could be parsed.
    The function is intentionally conservative:
      - Skips URLs that look like navigation/junk links.
      - PDFs are downloaded in full (truncation corrupts the structure).
      - HTML pages are capped at 256 KB to avoid hanging on large sites.
      - Silently swallows all errors (caller treats "" as "unknown").
    """
    if _is_junk_url(url):
        return ""

    try:
        import requests as _requests
        sess = session or _requests.Session()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

        is_pdf = url.lower().endswith(".pdf")

        if is_pdf:
            # Download full PDF — truncation corrupts the xref table
            resp = sess.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            raw = resp.content
            content_type = resp.headers.get("Content-Type", "").lower()
        else:
            # Stream HTML; cap at 256 KB
            resp = sess.get(url, timeout=timeout, headers=headers, stream=True)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "").lower()
            raw = b""
            for chunk in resp.iter_content(chunk_size=8192):
                raw += chunk
                if len(raw) >= 262144:
                    break

        # ── PDF path ──────────────────────────────────────────────────────────
        if "pdf" in content_type or is_pdf:
            text = ""
            try:
                import io
                import logging as _logging
                import pypdf
                # Suppress noisy pypdf warnings (malformed xref tables, EOF, etc.)
                _logging.getLogger("pypdf").setLevel(_logging.ERROR)
                reader = pypdf.PdfReader(io.BytesIO(raw))
                text_parts = []
                for page in reader.pages[:4]:
                    text_parts.append(page.extract_text() or "")
                text = " ".join(text_parts)
            except Exception:
                # pypdf failed (encrypted, malformed)
                text = ""

            # OCR fallback for scanned/image-only PDFs (common for NIT Calicut,
            # ISI Tezpur, etc.). This is optional and only runs when pypdf
            # yields no extractable text.
            if not clean_text(text):
                try:
                    from pdf2image import convert_from_bytes
                    import pytesseract

                    images = convert_from_bytes(
                        raw,
                        first_page=1,
                        last_page=2,
                        fmt="png",
                    )
                    ocr_parts = []
                    for img in images:
                        ocr_parts.append(pytesseract.image_to_string(img) or "")
                    text = " ".join(ocr_parts)
                except Exception:
                    # OCR not available (system deps missing) or conversion failed
                    return ""
        # ── HTML path ─────────────────────────────────────────────────────────
        elif "html" in content_type or not url.lower().endswith(
            (".pdf", ".docx", ".doc", ".xlsx", ".zip")
        ):
            try:
                from bs4 import BeautifulSoup as _BS
                soup = _BS(raw.decode("utf-8", errors="replace"), "lxml")
                # Remove script/style noise
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(" ", strip=True)
            except Exception:
                return ""
        else:
            # .docx / .doc / other binary – skip
            return ""

        deadline = _extract_deadline_from_text(clean_text(text))

        # If we extracted something that looks like a notice/reference number
        # instead of a real date (common on NIT Durgapur / MNNIT PDFs), drop it.
        if deadline and parse_deadline_date(deadline) is None:
            deadline = ""

        # ── Secondary: follow first .pdf link when HTML yields no date ────────
        if not deadline:
            try:
                from bs4 import BeautifulSoup as _BS2
                from urllib.parse import urljoin
                import io as _io
                import logging as _logging2
                import pypdf as _pypdf
                _soup2 = _BS2(raw.decode("utf-8", errors="replace"), "lxml")
                _seen_pdf_urls: set = set()
                for _a in _soup2.find_all("a", href=True):
                    _href = str(_a["href"]).strip()
                    if not _href.lower().endswith(".pdf"):
                        continue
                    if not _href.startswith("http"):
                        _href = urljoin(url, _href)
                    if _is_junk_url(_href):
                        continue
                    # Skip PDFs whose filename contains non-recruitment keywords
                    _fname_lower = _href.lower()
                    if any(
                        _frag in _fname_lower
                        for _frag in _JUNK_PDF_FILENAME_FRAGMENTS
                    ):
                        continue
                    # Deduplicate PDF URLs
                    if _href in _seen_pdf_urls:
                        continue
                    _seen_pdf_urls.add(_href)
                    try:
                        _pdf_resp = sess.get(_href, timeout=timeout, headers=headers)
                        _pdf_resp.raise_for_status()
                        _logging2.getLogger("pypdf").setLevel(_logging2.ERROR)
                        _reader = _pypdf.PdfReader(_io.BytesIO(_pdf_resp.content))
                        _pdf_text = " ".join(
                            _pg.extract_text() or "" for _pg in _reader.pages[:4]
                        )
                        _pdf_clean = clean_text(_pdf_text)
                        # Prefer keyword-proximate date (more reliable signal)
                        _pdf_deadline = ""
                        for _m in _DEADLINE_KEYWORDS_RE.finditer(_pdf_clean):
                            _window = _pdf_clean[_m.end(): _m.end() + 120]
                            _cands = extract_dates(_window)
                            for _rd in _cands:
                                if parse_deadline_date(_rd) is not None:
                                    _pdf_deadline = _rd
                                    break
                            if _pdf_deadline:
                                break
                        if _pdf_deadline:
                            deadline = _pdf_deadline
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        return deadline

    except Exception:
        return ""


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


def extract_eligibility(text):
    """Extract eligibility / qualification criteria from raw text.

    Looks for common patterns such as:
      - "Essential Qualification: M.Tech / B.Tech ..."
      - "Eligibility: Ph.D. in ..."
      - Standalone degree keywords (B.Tech, M.Tech, Ph.D, M.Sc, M.E., MBA ...)
    Returns a short human-readable string, or "" if nothing found.
    """
    if not text:
        return ""

    # 1. Try to grab a full labelled sentence: "Essential Qual...: <content>"
    labelled = re.search(
        r"(?:Essential\s+Qualifications?|Eligibility(?:\s+Criteria)?|"
        r"Required\s+Qualifications?|Minimum\s+Qualifications?)"
        r"[:/\s]+([^\.]{10,200})",
        text,
        re.IGNORECASE,
    )
    if labelled:
        return clean_text(labelled.group(1))

    # 2. Collect individual degree mentions
    degree_pattern = re.compile(
        r"\b(?:Ph\.?D\.?|M\.?Tech\.?|B\.?Tech\.?|M\.?Sc\.?|B\.?Sc\.?|"
        r"M\.?E\.?|B\.?E\.?|M\.?Phil\.?|MBA|MCA|B\.?Pharm\.?|M\.?Pharm\.?|"
        r"Post\s*Doctoral|Post-Doctoral|Graduate|Post\s*Graduate)\b",
        re.IGNORECASE,
    )
    degrees = degree_pattern.findall(text)
    if degrees:
        # Deduplicate while preserving order
        seen = set()
        unique_degrees = []
        for d in degrees:
            norm = d.upper().replace(".", "").replace(" ", "")
            if norm not in seen:
                seen.add(norm)
                unique_degrees.append(d)
        return " / ".join(unique_degrees[:4])  # cap at 4 to keep it brief

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

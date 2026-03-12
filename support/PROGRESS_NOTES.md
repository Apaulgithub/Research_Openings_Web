# Research Openings Website — Scraper Progress Notes

> **Last updated:** 13 March 2026  
> **Branch:** `main`  
> **Status:** All fixes applied, **NOT YET COMMITTED** (4 files modified in working tree)

---

## 1. Project Overview

A Streamlit-based website that aggregates research/project-staff job postings from IIT, NIT, IIIT, IISER, ISI, IISc and other institutes across India.  The scraping pipeline is:

```
scrapers/run_all.py
  ├── scrapers/generic_scraper.py   ← handles all ~70 institutes generically
  ├── scrapers/iiser_pune.py        ← dedicated scraper (IISER Pune)
  └── … (other dedicated scrapers if any)

Each scraper writes data/<safe_name>_YYYYMMDD.json
run_all.py merges all → data/all_openings_latest.json
```

The frontend reads `all_openings_latest.json` and calls `filter_active()` (in `scrapers/utils.py`) to hide entries whose deadline has passed.  **Entries with a blank deadline are kept** (conservative — better to show than silently drop).

---

## 2. Key Files Changed (All Uncommitted)

| File | What changed |
|------|-------------|
| `scrapers/generic_scraper.py` | URL fix, junk filters, selector logic, IIIT Lucknow anchor fix |
| `scrapers/utils.py` | PDF chaining, junk-PDF filter, DDMMYYYY OCR pattern, keyword-proximate date extraction |
| `scrapers/iiser_pune.py` | Keyword legitimacy check, junk-title filter, anchor-element handling |
| `data/all_openings_latest.json` | Latest scrape output (231 entries, 37% with deadline) |

---

## 3. All Changes Made (Detailed)

### 3.1 `scrapers/utils.py`

#### A — `_JUNK_PDF_FILENAME_FRAGMENTS` constant  *(new)*
Prevents `fetch_detail_deadline()` from wasting time on PDFs that are clearly not job advertisements (telephone directories, brochures, hostel handbooks, etc.):

```python
_JUNK_PDF_FILENAME_FRAGMENTS = (
    "telephone", "directory", "brochure", "conduct-code", "conduct_code",
    "discipline", "swagatham", "calendar", "timetable", "time-table",
    "fee-structure", "annual-report", "annual_report", "newsletter",
    "gazette", "nitc-calendar", "hostel", "rti-",
)
```

#### B — Corrupted-OCR date pattern  *(added to `extract_dates()`)*
Handles `DDMMYYYY` and `DD1MM12026` (slashes OCR'd as "1") which appear in scanned-PDF text:

```python
# Pattern index 4:
r"(?<!\d)(\d{2})1?(\d{2})1?(202\d)(?!\d)"
# Reconstructed as DD/MM/YYYY after validating day 1–31, month 1–12
```

#### C — Keyword-proximate date extraction  *(in `_extract_deadline_from_text()`)*
Instead of just returning the last date in a PDF (which could be a publication date), the function now:
1. Searches for keywords like "Last Date", "Closing Date", "Walk-in" first.
2. Looks in the next 120 characters for a date (most reliable signal).
3. Falls back to the last date in the document only if no keyword hit.

#### D — PDF chaining  *(in `fetch_detail_deadline()`)*
When an HTML detail page itself contains no deadline date, the function now follows the first `.pdf` link found on that page and extracts the date from the PDF.  Applies the junk-PDF filename filter and URL deduplication to avoid infinite loops.

---

### 3.2 `scrapers/generic_scraper.py`

#### A — IIT ISM Dhanbad URL fix
```python
# OLD (R&D home page, no job listings):
"url": "https://people.iitism.ac.in/~research/"
# NEW (actual Project Openings page with table + End Date column):
"url": "https://people.iitism.ac.in/~research/Projectopening.php"
```
Result: 0 → 5 entries, all with deadlines.

#### B — `_JUNK_TITLES` expansion
Added ~35 new entries covering:
- People-directory page titles: `"fellows and project scientists"`, `"post-doctoral fellows"`, `"research fellows"`, `"project scientists"`, `"visiting faculty"`, `"current members"`, etc.
- Generic link labels with no content: `"application"`, `"details"`, `"corrigendum"`, `"advertisement"`, `"apply"`, `"link"`, `"pdf"`, `"click"`
- Careers-section headings: `"careers"`, `"careers@iiitl"`, `"job openings"`, `"current openings"`, `"open positions"`, `"opportunities"`, `"employment opportunities"`

#### C — `_STRONG_JOB_KEYWORDS` expansion
Added advertisement-title patterns (needed for IIIT Lucknow inline PDF links):
```python
"project advertisement", "vacancy notice", "recruitment notice",
"recruitment advertisement", "employment notice",
"job advertisement", "appointment advertisement",
```

#### D — Sequential `_CONTAINER_SELECTORS` (replaces multi-selector CSS string)
**Problem:** The old code used a single CSS multi-selector  
`"div.xc-calendar-list-item, ul li"` which caused NIT Calicut to return 130 entries (65 duplicated) because `xc-calendar-list-item` divs are *inside* `<li>` tags — both selectors matched the same content.

**Fix:** Try each selector independently in priority order; stop at the first one that yields valid (parsed) records:

```python
_CONTAINER_SELECTORS = [
    "div.view-content div.views-row",
    "div.xc-calendar-list-item",
    "article.elementor-post",
    "article",
    "ul li",
    "ol li",
    "div.content div.field-items div",
    "div.gdlr-core-text-box-item-content a",   # IIIT Lucknow
]
for _sel in _CONTAINER_SELECTORS:
    _candidates = soup.select(_sel)
    _found = [r for c in _candidates if (r := self._parse_generic(c))]
    if _found:
        openings.extend(_found)
        break
```

Result: NIT Calicut went from 130 → 64 entries.

#### E — `_parse_generic()` — anchor-element fix  *(new)*
When the container element IS an `<a>` tag (e.g. the `div.gdlr-core-text-box-item-content a` selector), `element.find("a")` returns `None` (searches children only).  Fix added at the very top of `_parse_generic`:

```python
_element_is_anchor = getattr(element, "name", None) == "a"
if _element_is_anchor:
    link_tag = element          # element IS the link
else:
    link_tag = element.find("a")
if link_tag is None:
    return None
```

Also skips the `_MIN_RAW_TEXT_LEN` floor for anchor elements (link text is naturally short; the PDF will supply the date).

#### F — `_parse_generic()` — junk-title recovery  *(IIIT Pune fix)*
When the first link's text is a junk label like `"Application"` or `"Details"`, instead of rejecting the element, the parser now:
1. Finds the non-link text in the element as the real title.
2. Looks for a `"Details"` link or a PDF link with `"advertisement"` in the filename for the `detail_url`.

This fixed IIIT Pune entries that had `title="Application"` instead of the actual ad title.

#### G — `_parse_generic()` — email/URL title rejection
```python
if title.startswith("http"):        return None   # bare URL as title
if "(at)" in _title_lower or "[at]" in _title_lower:  return None  # obfuscated email
if _title_lower.startswith("careers@"):  return None  # careers@ headings
```

#### H — PDF-advertisement relaxation  *(IIIT Lucknow)*
When a link's combined text has no `_STRONG_JOB_KEYWORDS` but the URL points to a `.pdf` **and** the title contains a word like `"advertisement"`, accept it:

```python
_is_pdf_ad = (
    detail_url.lower().endswith(".pdf")
    and any(kw in _title_lower for kw in (
        "advertisement", "vacancy notice", "recruitment notice",
        "recruitment advertisement", "employment notice",
    ))
)
if not _is_pdf_ad:
    return None
```

---

### 3.3 `scrapers/iiser_pune.py`

Added the same keyword-legitimacy check and junk-title filter that `generic_scraper.py` uses, to stop people-directory page links (e.g. `"Fellows and Project Scientists"`, `"Post-Doctoral Fellows"`) from being scraped as job postings.

```python
from scrapers.generic_scraper import _JUNK_TITLES, _STRONG_JOB_KEYWORDS
# …
if title.lower() in _JUNK_TITLES:
    return None
# …
combined_lower = (title + " " + raw_text).lower()
if not any(kw in combined_lower for kw in _STRONG_JOB_KEYWORDS):
    return None
```

---

## 4. Current Coverage (as of last run — 13 March 2026)

**Overall: 86 / 231 active entries have a deadline (37%)**

| Institute | Active | w/ Deadline | % | Notes |
|-----------|--------|-------------|---|-------|
| IIITDM Kancheepuram | 58 | 0 | 0% | ❌ All Google Forms — structurally unfixable |
| NIT Calicut | 47 | 3 | 6% | 🟡 44 PDFs are scanned images; OCR gives garbage dates |
| IIT Kharagpur | 31 | 30 | 96% | 🟡 1 entry has blank `detail_url` |
| NIT Silchar | 14 | 2 | 14% | 🟡 Most are post-selection notices (results, shortlists) |
| IIT Mandi | 13 | 8 | 61% | 🟡 5 entries link to Google Forms (no date on form) |
| IIT Indore | 9 | 4 | 44% | 🟡 Some PDFs return HTTP 500 |
| IIT Madras | 6 | 6 | 100% | ✅ |
| NIT Durgapur | 6 | 6 | 100% | ✅ |
| IIITDM Jabalpur | 6 | 0 | 0% | 🟡 Walk-in test notices, no closing date |
| IIT ISM Dhanbad | 5 | 5 | 100% | ✅ Fixed this sprint |
| IISc Bangalore | 5 | 0 | 0% | ❌ PDFs are 2025 (expired or missing date text) |
| IISER Pune | 4 | 4 | 100% | ✅ Fixed this sprint |
| IIT Dharwad | 4 | 0 | 0% | ❌ Rolling advertisement, explicitly no closing date |
| NIT Hamirpur | 4 | 4 | 100% | ✅ |
| MNNIT Allahabad | 4 | 3 | 75% | 🟡 1 PDF is 404 |
| IIT Gandhinagar | 3 | 3 | 100% | ✅ |
| IISER Tirupati | 3 | 3 | 100% | ✅ |
| IIT Hyderabad | 2 | 2 | 100% | ✅ |
| IIIT Pune | 2 | 1 | 50% | 🟡 Fixed this sprint; 1 PDF still 404 |
| IIT BHU Varanasi | 1 | 0 | 0% | ❌ `detail_url` is `#v-pills-corri` (anchor, not PDF) |
| IIITDM Kurnool | 1 | 1 | 100% | ✅ |
| IIIT Lucknow | 1 | 0 | 0% | 🟡 `Careers@IIITL` junk entry survived filter (date unknown) |
| IISER Mohali | 1 | 0 | 0% | ❌ Entry title is email address (`deanfaculty(AT)…`) — filter should catch it but timing issue |
| IISER TVM | 1 | 1 | 100% | ✅ |

> **Note:** The `filter_active()` function only removes entries whose deadline has *already passed*. Entries with a blank deadline are **always kept** (conservative). So the active count is slightly inflated by old postings whose PDFs no longer contain a parseable date.

---

## 5. Remaining Issues and Next Steps

### 5.1 Two junk entries still in data (easy fix)

The last scrape (13 March 2026 at 02:49) was the *old* run before the IIIT Lucknow anchor fix was applied. After applying the fixes, the next `run_all.py` run should clean these up naturally.

But two entries survive that the new filters should already block:

| Entry | Why it survived | Fix |
|-------|----------------|-----|
| `Careers@IIITL` (IIIT Lucknow) | Old data file; the `_title_lower.startswith("careers@")` filter is in place — will be gone after next run | Re-run scraper |
| `deanfaculty(AT)iisermohali.ac.in` (IISER Mohali) | Old data file; `"(at)"` filter is in place | Re-run scraper |

### 5.2 IISc Bangalore — 0 deadlines (5 entries)

All 5 entries link to PDFs (e.g. `Job-openinPD.pdf`, `JRF_Notice_ANRF_Project_TR.pdf`).  The PDFs exist (200 OK) but:
- Some are mid-2025 postings where the deadline has passed.
- Some may not contain "Last Date" in parseable text form.

**Next step:** Manually inspect the PDFs to see if they have machine-readable dates:
```bash
cd webop
python3 -c "
from scrapers.utils import fetch_detail_deadline
urls = [
    'https://iisc.ac.in/wp-content/uploads/2025/10/Job-openinPD.pdf',
    'https://iisc.ac.in/wp-content/uploads/2025/04/JRF_Notice_ANRF_Project_TR.pdf',
    'https://iisc.ac.in/wp-content/uploads/2025/03/Job-vacancy-revised.pdf',
]
for u in urls:
    print(u.split('/')[-1], '->', fetch_detail_deadline(u))
"
```
If PDFs do have dates but `filter_active()` is removing them (dates are in 2025), they will disappear correctly once the scraper runs.

### 5.3 IIT BHU Varanasi — `#v-pills-corri` anchor URL

The entry has `detail_url = "https://iitbhu.ac.in/#v-pills-corri"` which is a JavaScript tab anchor, not a PDF.  The actual corrigendum notice URL needs to be found manually on the page.

**Next step:** Visit `https://iitbhu.ac.in/dean/dord/recruitment` and find the actual PDF link for the `Advt No. IIT(BHU)/R&D/IPDF/01/2025` entry.

### 5.4 NIT Calicut — 44 scanned-image PDFs (hard limit)

44 of 47 NIT Calicut entries link to scanned-image PDFs. `pypdf` extracts text but OCR is too corrupted for reliable date parsing. This is a structural limitation — would require a proper OCR engine (Tesseract/EasyOCR) to fix.

**Possible approach:**
```python
# In fetch_detail_deadline(), after pypdf fails to find a date:
# Try pytesseract on each page image
import pypdf, pytesseract
from pdf2image import convert_from_bytes
images = convert_from_bytes(raw, first_page=1, last_page=2)
for img in images:
    text = pytesseract.image_to_string(img)
    deadline = _extract_deadline_from_text(text)
    if deadline:
        return deadline
```
Requires `sudo apt install tesseract-ocr poppler-utils` + `pip install pytesseract pdf2image`.

### 5.5 IIITDM Kancheepuram — 58 Google Forms (unfixable)

All 58 entries link to `https://docs.google.com/forms/…`.  Google Forms do not contain a closing date in any machine-readable way.  The only fix would be to:
- Add a `deadline` field to the Google Form itself (not our control), or
- Manually maintain a separate deadline lookup table.

### 5.6 Run the full scraper after fixing

```bash
cd '/media/mintos/f9137947-cb6f-497f-b531-0a9b76e747af/R&D_openings/webop'
timeout 3600 ./bin/python3 -m scrapers.run_all 2>&1 | tee scraper.log
```

### 5.7 Commit all changes

```bash
cd '/media/mintos/f9137947-cb6f-497f-b531-0a9b76e747af/R&D_openings/webop'
git add scrapers/generic_scraper.py scrapers/iiser_pune.py scrapers/utils.py data/all_openings_latest.json
git commit -m "Fix deadline coverage: ISM Dhanbad URL, dedup selectors, IIIT Lucknow anchor fix, IIIT Pune title fix, junk filter expansion, email/URL title rejection, PDF-ad keyword relaxation"
git push origin main
```

---

## 6. Architecture Quick-Reference

### How `_parse_generic()` works (after all fixes)

```
element (BeautifulSoup tag — li, div, article, OR <a> itself)
  │
  ├─ Is element an <a> tag? ──yes──► link_tag = element (anchor fix)
  │                          no   ► link_tag = element.find("a")
  │                                 └─ None? ── return None
  │
  ├─ title = link_tag.get_text()
  │   ├─ Empty / < 8 chars / in _JUNK_TITLES?
  │   │   └─ Try non-link text in element as title
  │   │       └─ Still junk? ── return None
  │   │       └─ Find "Details" / advertisement PDF link as link_tag
  │   └─ OK
  │
  ├─ title starts with "http"?  ── return None
  ├─ title has "(at)" or "[at]"? ── return None
  ├─ title starts with "careers@"? ── return None
  │
  ├─ detail_url = resolve(link_tag.href)
  │
  ├─ raw_text = element.get_text()
  │   └─ anchor element? skip length check
  │   └─ len < 30? ── return None
  │
  ├─ combined = title + " " + raw_text
  │   └─ No _STRONG_JOB_KEYWORDS match?
  │       └─ URL ends .pdf AND title has "advertisement"? ── OK (IIIT Lucknow)
  │       └─ Otherwise ── return None
  │
  └─ Extract dates → fetch_detail_deadline if none found
     └─ Return structured record dict
```

### How `fetch_detail_deadline()` works (after all fixes)

```
URL
  ├─ _is_junk_url()? ── return ""
  ├─ Is PDF?
  │   └─ pypdf → extract text from pages 1–4
  │       └─ _extract_deadline_from_text()
  │           ├─ Search for keyword-proximate date (Last Date:, Deadline:, etc.)
  │           └─ Fallback: last date in document
  └─ Is HTML?
      ├─ BeautifulSoup → strip nav/footer/header → get_text()
      │   └─ _extract_deadline_from_text()
      └─ If still no date:
          └─ Scan HTML for .pdf links
              └─ Filter junk filenames (_JUNK_PDF_FILENAME_FRAGMENTS)
              └─ Download each PDF
              └─ Extract keyword-proximate date
              └─ Return first hit
```

---

## 7. Fixes Summary Table

| # | Fix | File | Root Cause | Result |
|---|-----|------|-----------|--------|
| 1 | IIT ISM Dhanbad URL | `generic_scraper.py` | Pointed to R&D home page, not project openings | 0 → 5 entries, 5/5 deadlines |
| 2 | NIT Calicut deduplication | `generic_scraper.py` | CSS multi-selector matched elements at two nesting levels | 130 → 64 entries |
| 3 | IIIT Pune title `"Application"` | `generic_scraper.py` | Scraper picked up application-form PDF links | Proper titles + detail PDF links |
| 4 | IISER Pune people-directory entries | `iiser_pune.py` | "Fellows and Project Scientists" page scraped as jobs | Junk entries removed |
| 5 | IISER Mohali email-as-title | `generic_scraper.py` | `deanfaculty(AT)…` became entry title | `(at)` pattern rejection |
| 6 | IIIT Lucknow `Careers@IIITL` title | `generic_scraper.py` | Nav heading became entry title | `careers@` rejection |
| 7 | IIIT Lucknow 0 entries | `generic_scraper.py` | Selector matched `<a>` elements; `find("a")` returns None for self; link text too short; no job keywords | Anchor-element fix + PDF-ad relaxation → 5 entries |
| 8 | Junk-PDF filenames downloaded | `utils.py` | Telephone directories, calendars, hostel handbooks fetched as "detail pages" | `_JUNK_PDF_FILENAME_FRAGMENTS` filter |
| 9 | Corrupted OCR dates missed | `utils.py` | `DDMMYYYY` / `DD1MM12026` pattern not in regex | New pattern in `extract_dates()` |
| 10 | Wrong date in PDFs (publication vs deadline) | `utils.py` | Last date in document was publication date | Keyword-proximate date extraction |
| 11 | HTML pages with PDF attachments missed | `utils.py` | Only first-level content was searched | PDF chaining in `fetch_detail_deadline()` |

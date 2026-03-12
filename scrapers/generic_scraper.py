"""Generic scraper that handles multiple institutes from the URLs registry.

This module provides a configurable scraper that can be instantiated for any
institute whose page follows a standard table-or-link layout.  For institutes
that require highly customised parsing, a dedicated scraper module should be
created instead.

INSTITUTE_REGISTRY contains every institute listed in support/URLs.md.
Each entry carries:
  name     - display name
  url      - recruitment page URL
  base     - base domain (for resolving relative links)
  network  - one of: IIT | NIT | IIIT | IISER | ISI
  selenium - whether Selenium is preferred (falls back to requests if Chrome
             is unavailable)
"""
import logging

from scrapers.utils import (
    BaseScraper, clean_text, extract_dates, extract_department,
    extract_eligibility, normalize_position_type, is_expired,
    fetch_detail_deadline,
)

logger = logging.getLogger(__name__)

# Titles that are clearly navigation / menu items, not actual job postings.
_JUNK_TITLES = {
    "home", "about", "about us", "contact", "contact us", "careers",
    "recruitment", "recruitments", "jobs", "news", "notices", "notice board",
    "announcements", "advertisement", "advertisements", "vacancies",
    "faculty", "staff", "students", "alumni", "research", "academics",
    "administration", "sitemap", "login", "intranet", "portal",
    "back", "next", "previous", "more", "view all", "read more",
    "introduction", "vision", "mission", "leadership", "gallery",
    "downloads", "forms", "tenders", "projects", "publications",
    "telephone directory", "dashboard", "library", "hostel", "placements",
    "notices & circulars", "job opportunities", "project positions",
    "temporary positions", "number of vacancies", "last date of application",
    "s.no", "sl.no", "sl no", "#", "sno",
    "title", "position", "post", "name", "name of the post",
    "department", "posting date", "last date",
    "pi name", "details", "date", "action",
    "contact person", "advertisement details",
    # Additional navigation / page-section headings
    "vision & mission", "goals", "core values", "about city", "connectivity",
    "board of governors", "senate members", "committees", "governance",
    "director", "director's message", "chairman bog", "at a glance",
    "background", "council", "iisers council", "vision mission",
    "how to reach", "reach us", "campus", "about campus", "about iit",
    "about nit", "about iiit", "about iiser", "about iisc",
    "head of department", "technical", "professional support staff",
    "directorate", "director's desk", "secretariat", "coordination forum",
    "nivahika", "directory", "senate", "building and works committee",
    "journey so far", "rankings", "reports", "acts", "rules", "statutes",
    "history", "legacy", "overview", "profile", "highlights",
    "fee structure", "admissions", "academics overview", "research overview",
    "events", "workshops", "seminars", "conferences", "tenders & quotations",
    "media", "press", "rti", "grievance", "feedback", "faq",
    "departments", "schools", "centres", "laboratories", "facilities",
    "sports", "cultural", "nss", "ncc", "clubs",
    "international", "collaborations", "industry", "consultancy",
    "alumni association", "endowment", "donation",
    "email", "phone", "address", "location", "map",
    "apply online", "apply now", "click here", "download", "view",
    "notification", "circular", "order", "memorandum",
    # People directory pages (not job postings)
    "fellows and project scientists", "post-doctoral fellows",
    "postdoctoral fellows", "research fellows", "project scientists",
    "visiting faculty", "adjunct faculty", "emeritus faculty",
    "faculty members", "faculty list", "research staff list",
    "current members", "group members", "team members",
    # Generic link labels (no content)
    "application", "details", "corrigendum", "advertisement",
    "apply", "apply here", "link", "pdf", "click",
    # Careers page headings (not individual postings)
    "careers", "careers@iiitl", "job openings", "current openings",
    "open positions", "opportunities", "employment opportunities",
}

# Minimum meaningful raw_text length for a record to be kept.
# Entries shorter than this are almost certainly nav links, not job postings.
_MIN_RAW_TEXT_LEN = 30

# Keywords that indicate an entry is a genuine job/research posting.
# _parse_generic uses this to reject nav items and news blurbs.
# These are split into "strong" (sufficient alone) and "context" (require
# at least two present or a strong indicator in the title).
_STRONG_JOB_KEYWORDS = {
    "jrf", "srf", "ra-i", "ra-ii", "ra-iii",
    "junior research fellow", "senior research fellow",
    "research associate", "research assistant", "research intern",
    "project associate", "project assistant", "project staff",
    "project scientist", "field investigator", "field assistant",
    "post-doctoral", "postdoctoral", "post doctoral",
    "walk-in", "walk in interview",
    "advertisement for the position", "advertisement for the post",
    "advertisement for recruitment", "application are invited",
    "applications are invited", "applications invited",
    "recruitment to the post", "engagement of",
    "advt. no", "advt no", "advt:",
    # IIT Bhubaneswar style: project-specific positions with [Last Date: …]
    "[last date:", "last date:", "last date :",
    # General short-form / common patterns
    "vacancy", "vacancies", "recruitment of",
    "post of ", "position of ", "positions of ",
    "project position", "project staff", "project fellow",
    "temporary position", "temporary post",
    "contractual appointment", "contract appointment",
    "purely temporary", "purely on contract",
    "one position", "two positions", "three positions",
    "no. of post", "number of post",
    # Advertisement-title patterns (e.g. IIIT Lucknow inline PDF links)
    "project advertisement", "vacancy notice", "recruitment notice",
    "recruitment advertisement", "employment notice",
    "job advertisement", "appointment advertisement",
}

# Heading keywords that signal the start of an "Archives" / "Past" section.
# When current_section_only=True the scraper stops at the first element whose
# text matches any of these.
_ARCHIVE_MARKERS = {
    "archive", "archives", "archives:", "past openings", "past advertisements",
    "closed positions", "expired", "previous openings",
}

INSTITUTE_REGISTRY = [
    # ------------------------------------------------------------------ IITs
    {"name": "IIT Roorkee",      "url": "https://iitr.ac.in/Careers/Project%20Jobs.html",                                               "base": "https://iitr.ac.in",          "network": "IIT",   "selenium": False},
    {"name": "IIT Guwahati",     "url": "https://iitg.ac.in/rndproj/recruitment/",                                                      "base": "https://iitg.ac.in",          "network": "IIT",   "selenium": False},
    {"name": "IIT Hyderabad",    "url": "https://iith.ac.in/careers/",                                                                  "base": "https://iith.ac.in",          "network": "IIT",   "selenium": False},
    {"name": "IIT Jodhpur",      "url": "https://erponline.iitj.ac.in/RnDOutside/projectTemporaryAppointment.htm",                      "base": "https://erponline.iitj.ac.in","network": "IIT",   "selenium": False},
    {"name": "IIT Indore",       "url": "https://www.iiti.ac.in/recruitments/project-positions",                                        "base": "https://www.iiti.ac.in",      "network": "IIT",   "selenium": False},
    {"name": "IIT BHU Varanasi", "url": "https://iitbhu.ac.in/dean/dord/recruitment",                                                   "base": "https://iitbhu.ac.in",        "network": "IIT",   "selenium": False},
    {"name": "IIT ISM Dhanbad",  "url": "https://people.iitism.ac.in/~research/Projectopening.php",                                        "base": "https://people.iitism.ac.in", "network": "IIT",   "selenium": False},
    {"name": "IIT Bhubaneswar",  "url": "https://www.iitbbs.ac.in/index.php/home/jobs/research-jobs/",                                  "base": "https://www.iitbbs.ac.in",    "network": "IIT",   "selenium": False},
    {"name": "IIT Gandhinagar",  "url": "https://iitgn.ac.in/careers/staff",                                                            "base": "https://iitgn.ac.in",         "network": "IIT",   "selenium": False},
    {"name": "IIT Patna",        "url": "https://www.iitp.ac.in/?option=com_content&view=article&id=1758:notice-board-list",            "base": "https://www.iitp.ac.in",      "network": "IIT",   "selenium": False},
    {"name": "IIT Mandi",        "url": "https://www.iitmandi.ac.in/recruitments/project",                                              "base": "https://www.iitmandi.ac.in",  "network": "IIT",   "selenium": False},
    {"name": "IIT Tirupati",     "url": "https://www.iittp.ac.in/Project_Positions",                                                    "base": "https://www.iittp.ac.in",     "network": "IIT",   "selenium": False},
    {"name": "IIT Palakkad",     "url": "https://iitpkd.ac.in/resstaffrect",                                                            "base": "https://iitpkd.ac.in",        "network": "IIT",   "selenium": False},
    {"name": "IIT Bhilai",       "url": "https://www.iitbhilai.ac.in/index.php?pid=rnd_staff_rec",                                     "base": "https://www.iitbhilai.ac.in", "network": "IIT",   "selenium": False},
    {"name": "IIT Goa",          "url": "https://iitgoa.ac.in/project-position/",                                                       "base": "https://iitgoa.ac.in",        "network": "IIT",   "selenium": False},
    {"name": "IIT Jammu",        "url": "https://iitjammu.ac.in/postlist/Jobs",                                                         "base": "https://iitjammu.ac.in",      "network": "IIT",   "selenium": False},
    {"name": "IIT Dharwad",      "url": "https://www.iitdh.ac.in/other-recruitments",                                                   "base": "https://www.iitdh.ac.in",     "network": "IIT",   "selenium": False},
    # ------------------------------------------------------------------ NITs
    {"name": "NIT Trichy",       "url": "https://www.nitt.edu/other/jobs",                                                              "base": "https://www.nitt.edu",        "network": "NIT",   "selenium": False},
    {"name": "NIT Surathkal",    "url": "https://www.nitk.ac.in/announcements",                                                         "base": "https://www.nitk.ac.in",      "network": "NIT",   "selenium": False},
    {"name": "NIT Rourkela",     "url": "https://www.nitrkl.ac.in/Home/FacultyStaff/SRICCECareerNotices",                               "base": "https://www.nitrkl.ac.in",    "network": "NIT",   "selenium": False},
    {"name": "NIT Durgapur",     "url": "https://nitdgp.ac.in/p/careers",                                                               "base": "https://nitdgp.ac.in",        "network": "NIT",   "selenium": False},
    {"name": "NIT Warangal",     "url": "https://nitw.ac.in/staffrecruit",                                                              "base": "https://nitw.ac.in",          "network": "NIT",   "selenium": False},
    {"name": "NIT Calicut",      "url": "https://nitc.ac.in/contract-adhoc-recruitment-project-staff",                                  "base": "https://nitc.ac.in",          "network": "NIT",   "selenium": False},
    {"name": "NIT Hamirpur",     "url": "https://nith.ac.in/advertisement-recruitments",                                                "base": "https://nith.ac.in",          "network": "NIT",   "selenium": False},
    {"name": "NIT Kurukshetra",  "url": "https://nitkkr.ac.in/jobs-nit-kkr/",                                                           "base": "https://nitkkr.ac.in",        "network": "NIT",   "selenium": False},
    {"name": "NIT Jamshedpur",   "url": "https://www.nitjsr.ac.in/Recruitments",                                                        "base": "https://www.nitjsr.ac.in",    "network": "NIT",   "selenium": False},
    {"name": "NIT Silchar",      "url": "https://www.nits.ac.in/recruitment-view-all",                                                  "base": "https://www.nits.ac.in",      "network": "NIT",   "selenium": False},
    {"name": "MNNIT Allahabad",  "url": "https://www.mnnit.ac.in/index.php/project-position",                                           "base": "https://www.mnnit.ac.in",     "network": "NIT",   "selenium": False},
    # ------------------------------------------------------------------ IIITs
    {"name": "IIIT Allahabad",   "url": "https://www.iiita.ac.in/announcements.php",                                                    "base": "https://www.iiita.ac.in",     "network": "IIIT",  "selenium": False},
    {"name": "IIITM Gwalior",    "url": "https://www.iiitm.ac.in/index.php/en/careers",                                                 "base": "https://www.iiitm.ac.in",     "network": "IIIT",  "selenium": False},
    {"name": "IIITDM Jabalpur",  "url": "https://www.iiitdmj.ac.in/pv.php",                                                             "base": "https://www.iiitdmj.ac.in",   "network": "IIIT",  "selenium": False},
    {"name": "IIITDM Kancheepuram", "url": "https://www.iiitdm.ac.in/recruitment/project-positions",                                    "base": "https://www.iiitdm.ac.in",    "network": "IIIT",  "selenium": False},
    {"name": "IIITDM Kurnool",   "url": "https://iiitk.ac.in/Project-Recruitments/page",                                               "base": "https://iiitk.ac.in",         "network": "IIIT",  "selenium": False},
    {"name": "IIIT Sri City",    "url": "https://iiits.ac.in/ticker/upcoming-events-announcements/",                                    "base": "https://iiits.ac.in",         "network": "IIIT",  "selenium": False},
    {"name": "IIIT Guwahati",    "url": "https://www.iiitg.ac.in/iitg_reqr?ct=RzNJNURKa005enFYa3RJWWtvM2cvQT09",                       "base": "https://www.iiitg.ac.in",     "network": "IIIT",  "selenium": False},
    {"name": "IIIT Kalyani",     "url": "https://iiitkalyani.ac.in/career",                                                             "base": "https://iiitkalyani.ac.in",   "network": "IIIT",  "selenium": False},
    {"name": "IIIT Lucknow",     "url": "https://iiitl.ac.in/index.php/project-vacancy/",                                               "base": "https://iiitl.ac.in",         "network": "IIIT",  "selenium": False},
    {"name": "IIIT Dharwad",     "url": "https://iiitdwd.ac.in/careers/",                                                               "base": "https://iiitdwd.ac.in",       "network": "IIIT",  "selenium": False},
    {"name": "IIIT Manipur",     "url": "https://iiitmanipur.ac.in/pages/recruitment/recruit.php",                                      "base": "https://iiitmanipur.ac.in",   "network": "IIIT",  "selenium": False},
    {"name": "IIIT Nagpur",      "url": "https://www.iiitn.ac.in/recruitments",                                                         "base": "https://www.iiitn.ac.in",     "network": "IIIT",  "selenium": False},
    {"name": "IIIT Pune",        "url": "https://iiitp.ac.in/careers",                                                                  "base": "https://iiitp.ac.in",         "network": "IIIT",  "selenium": False},
    {"name": "IIIT Ranchi",      "url": "https://iiitranchi.ac.in/Recruitments.aspx",                                                   "base": "https://iiitranchi.ac.in",    "network": "IIIT",  "selenium": False},
    {"name": "IIIT Surat",       "url": "https://iiitsurat.ac.in/career",                                                               "base": "https://iiitsurat.ac.in",     "network": "IIIT",  "selenium": False},
    {"name": "IIIT Bhopal",      "url": "https://iiitbhopal.ac.in/",                                                                    "base": "https://iiitbhopal.ac.in",    "network": "IIIT",  "selenium": False},
    {"name": "IIIT Bhagalpur",   "url": "https://www.iiitbh.ac.in/recruitment-2024",                                                    "base": "https://www.iiitbh.ac.in",    "network": "IIIT",  "selenium": False},
    {"name": "IIIT Agartala",    "url": "https://iiitagartala.ac.in/recruitment.html",                                                  "base": "https://iiitagartala.ac.in",  "network": "IIIT",  "selenium": False},
    {"name": "IIIT Naya Raipur", "url": "https://www.iiitnr.ac.in/employment-data",                                                     "base": "https://www.iiitnr.ac.in",    "network": "IIIT",  "selenium": False},
    {"name": "IIIT Una",         "url": "https://iiitu.ac.in/recruitment",                                                              "base": "https://iiitu.ac.in",         "network": "IIIT",  "selenium": False},
    {"name": "IIIT Tiruchirappalli", "url": "https://iiitt.ac.in/",                                                                     "base": "https://iiitt.ac.in",         "network": "IIIT",  "selenium": False},
    {"name": "IIIT Vadodara",    "url": "https://iiitvadodara.ac.in/staff_positions.php",                                               "base": "https://iiitvadodara.ac.in",  "network": "IIIT",  "selenium": False},
    {"name": "IIIT Kota",        "url": "https://iiitkota.ac.in/recruitment",                                                           "base": "https://iiitkota.ac.in",      "network": "IIIT",  "selenium": False},
    {"name": "IIIT Sonepat",     "url": "https://iiitsonepat.ac.in/",                                                                   "base": "https://iiitsonepat.ac.in",   "network": "IIIT",  "selenium": False},
    {"name": "IIIT Raichur",     "url": "https://iiitr.ac.in/careers",                                                                  "base": "https://iiitr.ac.in",         "network": "IIIT",  "selenium": False},
    {"name": "IIIT Kottayam",    "url": "https://www.iiitkottayam.ac.in/#!career",                                                      "base": "https://www.iiitkottayam.ac.in","network": "IIIT", "selenium": False},
    # ------------------------------------------------------------------ IISERs
    {"name": "IISER Kolkata",    "url": "https://www.iiserkol.ac.in/old/en/announcements/advertisement/",                               "base": "https://www.iiserkol.ac.in",  "network": "IISER", "selenium": False, "current_section_only": True},
    {"name": "IISER Mohali",     "url": "https://www.iisermohali.ac.in/project-positions",                                              "base": "https://www.iisermohali.ac.in","network": "IISER","selenium": False},
    {"name": "IISER Bhopal",     "url": "https://iiserb.ac.in/join_iiserb",                                                             "base": "https://iiserb.ac.in",        "network": "IISER", "selenium": False},
    {"name": "IISER TVM",        "url": "https://www.iisertvm.ac.in/openings",                                                          "base": "https://www.iisertvm.ac.in",  "network": "IISER", "selenium": False},
    {"name": "IISER Tirupati",   "url": "https://www.iisertirupati.ac.in/jobs/",                                                        "base": "https://www.iisertirupati.ac.in","network": "IISER","selenium": False},
    {"name": "IISER Berhampur",  "url": "https://www.iiserbpr.ac.in/opportunity/contractual",                                           "base": "https://www.iiserbpr.ac.in",  "network": "IISER", "selenium": False},
    # ------------------------------------------------------------------ ISIs
    {"name": "ISI Kolkata",      "url": "https://www.isical.ac.in/public/jobs",                                                         "base": "https://www.isical.ac.in",    "network": "ISI",   "selenium": False},
    {"name": "ISI Delhi",        "url": "https://www.isid.ac.in/~statmath/index.php?module=Academics",                                  "base": "https://www.isid.ac.in",      "network": "ISI",   "selenium": False},
    {"name": "ISI Bangalore",    "url": "https://www.isibang.ac.in/~eau/jobopportunities.htm",                                          "base": "https://www.isibang.ac.in",   "network": "ISI",   "selenium": False},
    {"name": "ISI Chennai",      "url": "https://isic.isichennai.res.in/assets/Oth/Jobs/",                                              "base": "https://isic.isichennai.res.in","network": "ISI",  "selenium": False},
    {"name": "ISI Tezpur",       "url": "https://www.isine.ac.in/careers.php",                                                          "base": "https://www.isine.ac.in",     "network": "ISI",   "selenium": False},
    # ----------------------------------------------------------- Other Institutes
    {"name": "IISc Bangalore",   "url": "https://iisc.ac.in/careers/contract-project-staff/",                                           "base": "https://iisc.ac.in",          "network": "Other", "selenium": False},
    {"name": "Jadavpur University","url": "https://jadavpuruniversity.in/notifications/",                                              "base": "https://jadavpuruniversity.in","network": "Other","selenium": False},
    {"name": "IIEST Shibpur",    "url": "https://www.iiests.ac.in/IIEST/Notices/?type=Employment",                                      "base": "https://www.iiests.ac.in",    "network": "Other", "selenium": False},
]


class GenericInstituteScraper(BaseScraper):
    """A configurable scraper for standard institute pages."""

    def __init__(self, name, url, base_url, use_selenium=False, network="",
                 current_section_only=False):
        super().__init__(
            institute_name=name,
            url=url,
            use_selenium=use_selenium,
        )
        self.base_url = base_url
        self.network = network
        # When True, stop scraping at the first "Archives / Past" heading so
        # only the current-openings section of the page is captured.
        self.current_section_only = current_section_only

    def scrape(self):
        """Scrape openings from the configured institute URL."""
        html = self.fetch_page()
        if html is None:
            self.logger.error("Failed to fetch %s page.", self.institute_name)
            return []

        soup = self.parse_html(html)
        if soup is None:
            return []

        openings = []

        if self.current_section_only:
            # Find the innermost <div> that directly contains both a <table>
            # and the archive marker as siblings, then walk its children in
            # order stopping at the archive marker.
            #
            # Fallback: if no such container is found, just use the first
            # table on the page.

            def _find_content_div(soup_obj):
                """Return the <div> whose direct children include a <table>
                AND a short archive-marker element as siblings."""
                for div in soup_obj.find_all("div"):
                    direct_tags = [c for c in div.children
                                   if hasattr(c, "name") and c.name]
                    has_table = any(c.name == "table" for c in direct_tags)
                    if not has_table:
                        continue
                    for c in direct_tags:
                        t = c.get_text(" ", strip=True).lower()
                        if len(t) < 80 and any(
                            m in t for m in _ARCHIVE_MARKERS
                        ):
                            return div
                return None

            content_div = _find_content_div(soup)

            if content_div is not None:
                archive_hit = False
                for child in content_div.children:
                    if not hasattr(child, "name") or not child.name:
                        continue
                    if archive_hit:
                        break
                    # Check for archive boundary
                    t = child.get_text(" ", strip=True).lower()
                    if len(t) < 80 and any(
                        m in t for m in _ARCHIVE_MARKERS
                    ):
                        self.logger.info(
                            "Stopping at archive marker <%s>: '%s'",
                            child.name, t[:60],
                        )
                        archive_hit = True
                        break
                    # Harvest tables at this level
                    if child.name == "table":
                        rows = child.find_all("tr")
                        for row in rows:
                            record = self._parse_table_row(row)
                            if record:
                                openings.append(record)
                    # Also find tables nested one level deep (e.g. inside a div)
                    elif child.name in ("div", "section"):
                        for tbl in child.find_all("table", recursive=False):
                            rows = tbl.find_all("tr")
                            for row in rows:
                                record = self._parse_table_row(row)
                                if record:
                                    openings.append(record)
            else:
                # Fallback: just take the very first table on the page
                first_table = soup.find("table")
                if first_table:
                    rows = first_table.find_all("tr")
                    for row in rows:
                        record = self._parse_table_row(row)
                        if record:
                            openings.append(record)
        else:
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    record = self._parse_table_row(row)
                    if record:
                        openings.append(record)

            if not openings:
                # Try each selector independently (in priority order) and use
                # the first one that yields valid records.  Using a single
                # multi-selector causes duplication when a more-specific
                # selector (e.g. div.xc-calendar-list-item) matches elements
                # that are also children of a less-specific one (ul li).
                _CONTAINER_SELECTORS = [
                    "div.view-content div.views-row",
                    "div.xc-calendar-list-item",
                    "article.elementor-post",
                    "article",
                    "ul li",
                    "ol li",
                    "div.content div.field-items div",
                    # Inline-link content areas (e.g. IIIT Lucknow's
                    # gdlr-core-text-box-item-content, generic p a, td a)
                    "div.gdlr-core-text-box-item-content a",
                ]
                for _sel in _CONTAINER_SELECTORS:
                    _candidates = soup.select(_sel)
                    _found = []
                    for container in _candidates:
                        record = self._parse_generic(container)
                        if record:
                            _found.append(record)
                    if _found:
                        openings.extend(_found)
                        break  # stop at first selector that produces results

        self.logger.info(
            "Scraped %d openings from %s.", len(openings), self.institute_name
        )
        self.save_to_json(openings)
        if self.use_selenium:
            self.cleanup()
        return openings

    def _resolve_url(self, href):
        """Turn a relative href into an absolute URL."""
        href = str(href)
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return self.base_url + href
        return self.base_url + "/" + href

    def _parse_table_row(self, row):
        """Extract fields from a table row."""
        cells = row.find_all("td")
        if len(cells) < 2:
            return None

        title = clean_text(cells[0].get_text())
        # If first cell is empty, a serial number, or just a digit string,
        # the actual title is probably in the second cell (e.g. NIT Hamirpur).
        if (not title or title.lower() in _JUNK_TITLES or len(title) < 6
                or title.isdigit()):
            title = clean_text(cells[1].get_text())
        if not title or title.lower() in _JUNK_TITLES:
            return None
        # Drop very short strings (likely index numbers or single letters)
        if len(title) < 6:
            return None

        link_tag = row.find("a")
        detail_url = ""
        if link_tag and link_tag.get("href"):
            detail_url = self._resolve_url(link_tag["href"])

        # Use a space separator so adjacent cell texts don't run together
        # (fixes cases like "Click here20.03.2026" → "Click here 20.03.2026")
        raw_text = clean_text(row.get_text(" ", strip=True))
        if len(raw_text) < _MIN_RAW_TEXT_LEN:
            return None

        # Keyword-legitimacy check: skip rows that are not actual job postings
        # (e.g. PhD admission lists, exam results, faculty lists).
        combined_lower = (title + " " + raw_text).lower()
        if not any(kw in combined_lower for kw in _STRONG_JOB_KEYWORDS):
            return None

        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""
        if not deadline and detail_url:
            deadline = fetch_detail_deadline(detail_url, session=self.session)
        department = extract_department(raw_text)
        eligibility = extract_eligibility(raw_text)

        return {
            "institute": self.institute_name,
            "network": self.network,
            "department": department,
            "eligibility": eligibility,
            "title": title,
            "position_type": normalize_position_type(title),
            "deadline": deadline,
            "detail_url": detail_url,
            "raw_text": raw_text,
            "hash": self.generate_hash(title + detail_url),
        }

    def _parse_generic(self, element):
        """Fallback parser for non-table layouts."""
        # When the container element IS itself an <a> tag (e.g. when the CSS
        # selector targets anchors directly, like "div.foo a"), use the element
        # itself as the link_tag — element.find("a") searches only children.
        _element_is_anchor = getattr(element, "name", None) == "a"
        if _element_is_anchor:
            link_tag = element
        else:
            link_tag = element.find("a")
        if link_tag is None:
            return None

        title = clean_text(link_tag.get_text())

        # If the first link's text is a junk label (e.g. "Application",
        # "Details"), look for non-link text in the element that could serve
        # as the actual job title (e.g. IIIT Pune's div.career-div-left).
        if not title or len(title) < 8 or title.lower() in _JUNK_TITLES:
            # Try to find a non-anchor text node or dedicated title element
            title_el = element.find(class_=lambda c: c and "title" in c.lower())
            if title_el is None:
                # Fall back: collect non-link text from the element
                raw_non_link = " ".join(
                    chunk for chunk in element.strings
                    if chunk.strip() and not any(
                        chunk.strip() == a.get_text(strip=True)
                        for a in element.find_all("a")
                    )
                )
                title = clean_text(raw_non_link)
            else:
                title = clean_text(title_el.get_text())
            if not title or len(title) < 8 or title.lower() in _JUNK_TITLES:
                return None
            # The first link was a junk label — find the "Details" or main link
            # (prefer a link that points to a PDF advertisement over the
            # "Application" form link).
            for a in element.find_all("a", href=True):
                lbl = clean_text(a.get_text()).lower()
                href = a.get("href", "")
                if lbl in ("details",) or ("advertisement" in href.lower() and ".pdf" in href.lower()):
                    link_tag = a
                    break

        if not title or title.lower() in _JUNK_TITLES:
            return None

        # Reject email addresses and bare URLs as titles
        # (e.g. "deanfaculty(AT)iisermohali.ac.in" or "Careers@IIITL")
        _title_lower = title.lower()
        if title.startswith("http"):
            return None
        # Obfuscated email pattern: word(AT)domain or word[at]domain
        if "(at)" in _title_lower or "[at]" in _title_lower:
            return None
        # Careers page heading pattern
        if _title_lower.startswith("careers@"):
            return None

        detail_url = ""
        if link_tag.get("href"):
            detail_url = self._resolve_url(link_tag["href"])

        raw_text = clean_text(element.get_text())
        # When the container element IS the <a> tag (e.g. selectors like
        # "div.gdlr-core-text-box-item-content a"), raw_text == link text.
        # Use the title as raw_text in that case; skip the length floor.
        if not _element_is_anchor and len(raw_text) < _MIN_RAW_TEXT_LEN:
            return None

        # Keyword-legitimacy check: the combined text (title + raw_text) must
        # contain at least one strong job/recruitment keyword.  This blocks nav
        # menu entries, news blurbs, and CMS sidebar links.
        combined_lower = (title + " " + raw_text).lower()
        if not any(kw in combined_lower for kw in _STRONG_JOB_KEYWORDS):
            # Special relaxation: a link pointing to a PDF whose title contains
            # "advertisement" is almost certainly a job posting (e.g. IIIT Lucknow).
            _is_pdf_ad = (
                detail_url.lower().endswith(".pdf")
                and any(kw in _title_lower for kw in (
                    "advertisement", "vacancy notice", "recruitment notice",
                    "recruitment advertisement", "employment notice",
                ))
            )
            if not _is_pdf_ad:
                return None

        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""
        if not deadline and detail_url:
            deadline = fetch_detail_deadline(detail_url, session=self.session)
        department = extract_department(raw_text)
        eligibility = extract_eligibility(raw_text)

        return {
            "institute": self.institute_name,
            "network": self.network,
            "department": department,
            "eligibility": eligibility,
            "title": title,
            "position_type": normalize_position_type(title),
            "deadline": deadline,
            "detail_url": detail_url,
            "raw_text": raw_text,
            "hash": self.generate_hash(title + detail_url),
        }


def scrape_all_generic():
    """Run the generic scraper for every institute in the registry."""
    all_openings = []
    for entry in INSTITUTE_REGISTRY:
        scraper = GenericInstituteScraper(
            name=entry["name"],
            url=entry["url"],
            base_url=entry["base"],
            use_selenium=entry.get("selenium", False),
            network=entry.get("network", ""),
            current_section_only=entry.get("current_section_only", False),
        )
        try:
            results = scraper.scrape()
            all_openings.extend(results)
        except Exception as exc:
            logger.error("Scraper failed for %s: %s", entry["name"], exc)
    logger.info("Total generic openings scraped: %d", len(all_openings))
    return all_openings


if __name__ == "__main__":
    scrape_all_generic()

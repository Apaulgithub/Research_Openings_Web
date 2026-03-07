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
    extract_eligibility, normalize_position_type,
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
    "title", "position", "post", "name",
    "department", "posting date", "last date",
    "pi name", "details", "date", "action",
}

INSTITUTE_REGISTRY = [
    # ------------------------------------------------------------------ IITs
    {"name": "IIT Roorkee",      "url": "https://iitr.ac.in/Careers/Project%20Jobs.html",                                               "base": "https://iitr.ac.in",          "network": "IIT",   "selenium": False},
    {"name": "IIT Guwahati",     "url": "https://iitg.ac.in/rndproj/recruitment/",                                                      "base": "https://iitg.ac.in",          "network": "IIT",   "selenium": False},
    {"name": "IIT Hyderabad",    "url": "https://iith.ac.in/careers/",                                                                  "base": "https://iith.ac.in",          "network": "IIT",   "selenium": False},
    {"name": "IIT Jodhpur",      "url": "https://erponline.iitj.ac.in/RnDOutside/projectTemporaryAppointment.htm",                      "base": "https://erponline.iitj.ac.in","network": "IIT",   "selenium": True},
    {"name": "IIT Indore",       "url": "https://www.iiti.ac.in/recruitments/project-positions",                                        "base": "https://www.iiti.ac.in",      "network": "IIT",   "selenium": False},
    {"name": "IIT BHU Varanasi", "url": "https://iitbhu.ac.in/dean/dord/recruitment",                                                   "base": "https://iitbhu.ac.in",        "network": "IIT",   "selenium": False},
    {"name": "IIT ISM Dhanbad",  "url": "https://people.iitism.ac.in/~research/",                                                       "base": "https://people.iitism.ac.in", "network": "IIT",   "selenium": False},
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
    {"name": "IISER Kolkata",    "url": "https://www.iiserkol.ac.in/old/en/announcements/advertisement/",                               "base": "https://www.iiserkol.ac.in",  "network": "IISER", "selenium": False},
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
]


class GenericInstituteScraper(BaseScraper):
    """A configurable scraper for standard institute pages."""

    def __init__(self, name, url, base_url, use_selenium=False, network=""):
        super().__init__(
            institute_name=name,
            url=url,
            use_selenium=use_selenium,
        )
        self.base_url = base_url
        self.network = network

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

        tables = soup.find_all("table")
        for table in tables:
            body = table.find("tbody")
            rows = body.find_all("tr") if body else table.find_all("tr")
            for row in rows:
                record = self._parse_table_row(row)
                if record:
                    openings.append(record)

        if not openings:
            containers = soup.select(
                "div.view-content div.views-row, "
                "ul li, "
                "article, "
                "div.content div.field-items div"
            )
            for container in containers:
                record = self._parse_generic(container)
                if record:
                    openings.append(record)

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
        if not title or title.lower() in _JUNK_TITLES:
            return None
        # Drop very short strings (likely index numbers or single letters)
        if len(title) < 6:
            return None

        link_tag = row.find("a")
        detail_url = ""
        if link_tag and link_tag.get("href"):
            detail_url = self._resolve_url(link_tag["href"])

        raw_text = clean_text(row.get_text())
        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""
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
        link_tag = element.find("a")
        if link_tag is None:
            return None

        title = clean_text(link_tag.get_text())
        if not title or len(title) < 8:
            return None
        if title.lower() in _JUNK_TITLES:
            return None

        detail_url = ""
        if link_tag.get("href"):
            detail_url = self._resolve_url(link_tag["href"])

        raw_text = clean_text(element.get_text())
        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""
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

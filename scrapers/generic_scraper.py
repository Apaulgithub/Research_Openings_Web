"""Generic scraper that handles multiple institutes from the URLs registry.

This module provides a configurable scraper that can be instantiated for any
institute whose page follows a standard table-or-link layout.  For institutes
that require highly customised parsing, a dedicated scraper module should be
created instead.
"""
import logging
from typing import Optional

from scrapers.utils import BaseScraper, clean_text, extract_dates, normalize_position_type

logger = logging.getLogger(__name__)

INSTITUTE_REGISTRY = [
    {"name": "IIT Roorkee", "url": "https://iitr.ac.in/Careers/Project%20Jobs.html", "base": "https://iitr.ac.in", "selenium": False},
    {"name": "IIT Guwahati", "url": "https://iitg.ac.in/rndproj/recruitment/", "base": "https://iitg.ac.in", "selenium": False},
    {"name": "IIT Hyderabad", "url": "https://iith.ac.in/careers/", "base": "https://iith.ac.in", "selenium": False},
    {"name": "IIT Indore", "url": "https://www.iiti.ac.in/recruitments/project-positions", "base": "https://www.iiti.ac.in", "selenium": False},
    {"name": "IIT BHU Varanasi", "url": "https://iitbhu.ac.in/dean/dord/recruitment", "base": "https://iitbhu.ac.in", "selenium": False},
    {"name": "IIT Bhubaneswar", "url": "https://www.iitbbs.ac.in/index.php/home/jobs/research-jobs/", "base": "https://www.iitbbs.ac.in", "selenium": False},
    {"name": "IIT Gandhinagar", "url": "https://iitgn.ac.in/careers/staff", "base": "https://iitgn.ac.in", "selenium": False},
    {"name": "IIT Mandi", "url": "https://www.iitmandi.ac.in/recruitments/project", "base": "https://www.iitmandi.ac.in", "selenium": False},
    {"name": "IIT Tirupati", "url": "https://www.iittp.ac.in/Project_Positions", "base": "https://www.iittp.ac.in", "selenium": False},
    {"name": "IIT Palakkad", "url": "https://iitpkd.ac.in/resstaffrect", "base": "https://iitpkd.ac.in", "selenium": False},
    {"name": "IIT Bhilai", "url": "https://www.iitbhilai.ac.in/index.php?pid=rnd_staff_rec", "base": "https://www.iitbhilai.ac.in", "selenium": False},
    {"name": "IIT Goa", "url": "https://iitgoa.ac.in/project-position/", "base": "https://iitgoa.ac.in", "selenium": False},
    {"name": "IIT Jammu", "url": "https://iitjammu.ac.in/postlist/Jobs", "base": "https://iitjammu.ac.in", "selenium": False},
    {"name": "IIT Dharwad", "url": "https://www.iitdh.ac.in/other-recruitments", "base": "https://www.iitdh.ac.in", "selenium": False},
    {"name": "IIT Jodhpur", "url": "https://erponline.iitj.ac.in/RnDOutside/projectTemporaryAppointment.htm", "base": "https://erponline.iitj.ac.in", "selenium": True},
    {"name": "IIT ISM Dhanbad", "url": "https://people.iitism.ac.in/~research/", "base": "https://people.iitism.ac.in", "selenium": False},
    {"name": "IIT Patna", "url": "https://www.iitp.ac.in/?option=com_content&view=article&id=1758:notice-board-list", "base": "https://www.iitp.ac.in", "selenium": False},
    {"name": "NIT Trichy", "url": "https://www.nitt.edu/other/jobs", "base": "https://www.nitt.edu", "selenium": False},
    {"name": "NIT Surathkal", "url": "https://www.nitk.ac.in/announcements", "base": "https://www.nitk.ac.in", "selenium": False},
    {"name": "NIT Rourkela", "url": "https://www.nitrkl.ac.in/Home/FacultyStaff/SRICCECareerNotices", "base": "https://www.nitrkl.ac.in", "selenium": False},
    {"name": "NIT Durgapur", "url": "https://nitdgp.ac.in/p/careers", "base": "https://nitdgp.ac.in", "selenium": False},
    {"name": "NIT Warangal", "url": "https://nitw.ac.in/staffrecruit", "base": "https://nitw.ac.in", "selenium": False},
    {"name": "NIT Calicut", "url": "https://nitc.ac.in/contract-adhoc-recruitment-project-staff", "base": "https://nitc.ac.in", "selenium": False},
    {"name": "NIT Hamirpur", "url": "https://nith.ac.in/advertisement-recruitments", "base": "https://nith.ac.in", "selenium": False},
    {"name": "NIT Kurukshetra", "url": "https://nitkkr.ac.in/jobs-nit-kkr/", "base": "https://nitkkr.ac.in", "selenium": False},
    {"name": "NIT Jamshedpur", "url": "https://www.nitjsr.ac.in/Recruitments", "base": "https://www.nitjsr.ac.in", "selenium": False},
    {"name": "NIT Silchar", "url": "https://www.nits.ac.in/recruitment-view-all", "base": "https://www.nits.ac.in", "selenium": False},
    {"name": "MNNIT Allahabad", "url": "https://www.mnnit.ac.in/index.php/project-position", "base": "https://www.mnnit.ac.in", "selenium": False},
    {"name": "IISER Kolkata", "url": "https://www.iiserkol.ac.in/old/en/announcements/advertisement/", "base": "https://www.iiserkol.ac.in", "selenium": False},
    {"name": "IISER Mohali", "url": "https://www.iisermohali.ac.in/project-positions", "base": "https://www.iisermohali.ac.in", "selenium": False},
    {"name": "IISER Bhopal", "url": "https://iiserb.ac.in/join_iiserb", "base": "https://iiserb.ac.in", "selenium": False},
    {"name": "IISER TVM", "url": "https://www.iisertvm.ac.in/openings", "base": "https://www.iisertvm.ac.in", "selenium": False},
    {"name": "IISER Tirupati", "url": "https://www.iisertirupati.ac.in/jobs/", "base": "https://www.iisertirupati.ac.in", "selenium": False},
    {"name": "IISER Berhampur", "url": "https://www.iiserbpr.ac.in/opportunity/contractual", "base": "https://www.iiserbpr.ac.in", "selenium": False},
    {"name": "ISI Kolkata", "url": "https://www.isical.ac.in/public/jobs", "base": "https://www.isical.ac.in", "selenium": False},
    {"name": "ISI Delhi", "url": "https://www.isid.ac.in/~statmath/index.php?module=Academics", "base": "https://www.isid.ac.in", "selenium": False},
    {"name": "ISI Bangalore", "url": "https://www.isibang.ac.in/~eau/jobopportunities.htm", "base": "https://www.isibang.ac.in", "selenium": False},
]


class GenericInstituteScraper(BaseScraper):
    """A configurable scraper for standard institute pages."""

    def __init__(self, name, url, base_url, use_selenium=False):
        super().__init__(
            institute_name=name,
            url=url,
            use_selenium=use_selenium,
        )
        self.base_url = base_url

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
        if not title or title.lower() in (
            "s.no", "sl.no", "sl no", "#", "sno",
            "title", "position", "post", "name",
        ):
            return None

        link_tag = row.find("a")
        detail_url = ""
        if link_tag and link_tag.get("href"):
            detail_url = self._resolve_url(link_tag["href"])

        raw_text = clean_text(row.get_text())
        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""

        return {
            "institute": self.institute_name,
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

        detail_url = ""
        if link_tag.get("href"):
            detail_url = self._resolve_url(link_tag["href"])

        raw_text = clean_text(element.get_text())
        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""

        return {
            "institute": self.institute_name,
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

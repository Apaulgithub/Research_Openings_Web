import logging

from scrapers.utils import BaseScraper, clean_text, extract_dates, normalize_position_type

logger = logging.getLogger(__name__)


class IITKharagpurScraper(BaseScraper):
    """Scraper for IIT Kharagpur SRIC staff recruitment."""

    def __init__(self):
        super().__init__(
            institute_name="IIT Kharagpur",
            url="https://erp.iitkgp.ac.in/SRICStaffRecruitment/Advertise.jsp",
            use_selenium=True,
        )

    def scrape(self):
        """Scrape project staff openings from IIT Kharagpur SRIC portal."""
        html = self.fetch_page()
        if html is None:
            self.logger.error("Failed to fetch IIT Kharagpur page.")
            return []

        soup = self.parse_html(html)
        if soup is None:
            return []

        openings = []
        table = soup.find("table")
        if table:
            body = table.find("tbody")
            rows = body.find_all("tr") if body else table.find_all("tr")
            for row in rows:
                record = self._parse_row(row)
                if record:
                    openings.append(record)

        self.logger.info("Scraped %d openings from IIT Kharagpur.", len(openings))
        self.save_to_json(openings)
        self.cleanup()
        return openings

    def _parse_row(self, row):
        """Extract fields from a table row."""
        cells = row.find_all("td")
        if len(cells) < 2:
            return None

        title = clean_text(cells[0].get_text())
        if not title or title.lower() in ("s.no", "sl.no", "#", "advertisement"):
            return None

        link_tag = row.find("a")
        detail_url = ""
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            if href.startswith("/"):
                detail_url = "https://erp.iitkgp.ac.in" + href
            elif href.startswith("http"):
                detail_url = href

        raw_text = clean_text(row.get_text())
        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""

        return {
            "institute": "IIT Kharagpur",
            "network": "IIT",
            "title": title,
            "position_type": normalize_position_type(title),
            "deadline": deadline,
            "detail_url": detail_url,
            "raw_text": raw_text,
            "hash": self.generate_hash(title + detail_url),
        }


if __name__ == "__main__":
    scraper = IITKharagpurScraper()
    results = scraper.scrape()
    for item in results:
        logger.info("Found: %s | Deadline: %s", item["title"], item["deadline"])

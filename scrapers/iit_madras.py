import logging

from scrapers.utils import BaseScraper, clean_text, extract_dates, normalize_position_type

logger = logging.getLogger(__name__)


class IITMadrasScraper(BaseScraper):
    """Scraper for IIT Madras IC&SR current openings."""

    def __init__(self):
        super().__init__(
            institute_name="IIT Madras",
            url="https://icsrstaff.iitm.ac.in/careers/current_openings.php",
            use_selenium=False,
        )

    def scrape(self):
        """Scrape project staff openings from IIT Madras IC&SR portal."""
        html = self.fetch_page()
        if html is None:
            self.logger.error("Failed to fetch IIT Madras page.")
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
                record = self._parse_row(row)
                if record:
                    openings.append(record)

        if not tables:
            links = soup.find_all("a", href=True)
            for link in links:
                text = clean_text(link.get_text())
                if not text or len(text) < 10:
                    continue
                href = str(link["href"])
                if href.startswith("/"):
                    href = "https://icsrstaff.iitm.ac.in" + href
                dates = extract_dates(text)
                deadline = dates[-1] if dates else ""
                openings.append({
                    "institute": "IIT Madras",
                    "title": text,
                    "position_type": normalize_position_type(text),
                    "deadline": deadline,
                    "detail_url": href,
                    "raw_text": text,
                    "hash": self.generate_hash(text + href),
                })

        self.logger.info("Scraped %d openings from IIT Madras.", len(openings))
        self.save_to_json(openings)
        return openings

    def _parse_row(self, row):
        """Extract fields from a single table row."""
        cells = row.find_all("td")
        if len(cells) < 2:
            return None

        title = clean_text(cells[0].get_text())
        if not title or title.lower() in ("s.no", "sl.no", "sl no", "#", "sno"):
            return None

        link_tag = row.find("a")
        detail_url = ""
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            if href.startswith("/"):
                detail_url = "https://icsrstaff.iitm.ac.in" + href
            elif href.startswith("http"):
                detail_url = href

        raw_text = clean_text(row.get_text())
        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""

        return {
            "institute": "IIT Madras",
            "title": title,
            "position_type": normalize_position_type(title),
            "deadline": deadline,
            "detail_url": detail_url,
            "raw_text": raw_text,
            "hash": self.generate_hash(title + detail_url),
        }


if __name__ == "__main__":
    scraper = IITMadrasScraper()
    results = scraper.scrape()
    for item in results:
        logger.info("Found: %s | Deadline: %s", item["title"], item["deadline"])

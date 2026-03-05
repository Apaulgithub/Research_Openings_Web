import logging

from scrapers.utils import BaseScraper, clean_text, extract_dates, extract_department, normalize_position_type

logger = logging.getLogger(__name__)


class IITDelhiScraper(BaseScraper):
    """Scraper for IIT Delhi IRD current openings."""

    def __init__(self):
        super().__init__(
            institute_name="IIT Delhi",
            url="https://ird.iitd.ac.in/current-openings",
            use_selenium=True,
        )

    def scrape(self):
        """Scrape project staff openings from IIT Delhi IRD portal."""
        html = self.fetch_page()
        if html is None:
            self.logger.error("Failed to fetch IIT Delhi page.")
            return []

        soup = self.parse_html(html)
        if soup is None:
            return []

        openings = []
        table = soup.find("table")
        if table is None:
            rows = soup.select("div.view-content div.views-row")
            for row in rows:
                record = self._parse_div_row(row)
                if record:
                    openings.append(record)
        else:
            body = table.find("tbody")
            rows = body.find_all("tr") if body else table.find_all("tr")[1:]
            for row in rows:
                record = self._parse_table_row(row)
                if record:
                    openings.append(record)

        self.logger.info("Scraped %d openings from IIT Delhi.", len(openings))
        self.save_to_json(openings)
        self.cleanup()
        return openings

    def _parse_table_row(self, row):
        """Extract fields from a table row."""
        cells = row.find_all("td")
        if len(cells) < 2:
            return None

        title = clean_text(cells[0].get_text())
        if not title:
            return None

        link_tag = cells[0].find("a") or row.find("a")
        detail_url = ""
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            if href.startswith("/"):
                detail_url = "https://ird.iitd.ac.in" + href
            elif href.startswith("http"):
                detail_url = href

        raw_text = clean_text(row.get_text())
        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""
        department = extract_department(raw_text)

        return {
            "institute": "IIT Delhi",
            "network": "IIT",
            "department": department,
            "title": title,
            "position_type": normalize_position_type(title),
            "deadline": deadline,
            "detail_url": detail_url,
            "raw_text": raw_text,
            "hash": self.generate_hash(title + detail_url),
        }

    def _parse_div_row(self, row):
        """Extract fields from a div-based listing."""
        title_tag = row.find(["h3", "h4", "h2", "a", "span"])
        if title_tag is None:
            return None

        title = clean_text(title_tag.get_text())
        if not title:
            return None

        link_tag = row.find("a")
        detail_url = ""
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            if href.startswith("/"):
                detail_url = "https://ird.iitd.ac.in" + href
            elif href.startswith("http"):
                detail_url = href

        raw_text = clean_text(row.get_text())
        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""
        department = extract_department(raw_text)

        return {
            "institute": "IIT Delhi",
            "network": "IIT",
            "department": department,
            "title": title,
            "position_type": normalize_position_type(title),
            "deadline": deadline,
            "detail_url": detail_url,
            "raw_text": raw_text,
            "hash": self.generate_hash(title + detail_url),
        }


if __name__ == "__main__":
    scraper = IITDelhiScraper()
    results = scraper.scrape()
    for item in results:
        logger.info("Found: %s | Deadline: %s", item["title"], item["deadline"])

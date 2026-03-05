import logging

from scrapers.utils import BaseScraper, clean_text, extract_dates, extract_department, normalize_position_type

logger = logging.getLogger(__name__)


class IITKanpurScraper(BaseScraper):
    """Scraper for IIT Kanpur DORD project vacancies."""

    def __init__(self):
        super().__init__(
            institute_name="IIT Kanpur",
            url="https://www.iitk.ac.in/dord/project-vacancies",
            use_selenium=False,
        )

    def scrape(self):
        """Scrape project staff openings from IIT Kanpur DORD portal."""
        html = self.fetch_page()
        if html is None:
            self.logger.error("Failed to fetch IIT Kanpur page.")
            return []

        soup = self.parse_html(html)
        if soup is None:
            return []

        openings = []
        table = soup.find("table")
        if table:
            body = table.find("tbody")
            rows = body.find_all("tr") if body else table.find_all("tr")[1:]
            for row in rows:
                record = self._parse_row(row)
                if record:
                    openings.append(record)
        else:
            items = soup.select(
                "div.field-items li, "
                "div.view-content div.views-row, "
                "article"
            )
            for item in items:
                record = self._parse_generic(item)
                if record:
                    openings.append(record)

        self.logger.info("Scraped %d openings from IIT Kanpur.", len(openings))
        self.save_to_json(openings)
        return openings

    def _parse_row(self, row):
        """Extract fields from a table row."""
        cells = row.find_all("td")
        if len(cells) < 2:
            return None

        title = clean_text(cells[0].get_text())
        if not title or title.lower() in (
            "s.no", "sl.no", "#", "post", "title",
            "department", "posting date", "last date",
            "pi name", "details", "action",
        ):
            return None

        link_tag = row.find("a")
        detail_url = ""
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            if href.startswith("/"):
                detail_url = "https://www.iitk.ac.in" + href
            elif href.startswith("http"):
                detail_url = href

        raw_text = clean_text(row.get_text())
        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""
        department = extract_department(raw_text)

        return {
            "institute": "IIT Kanpur",
            "network": "IIT",
            "department": department,
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
        if not title or len(title) < 5:
            return None

        href = link_tag.get("href", "")
        if href.startswith("/"):
            href = "https://www.iitk.ac.in" + href

        raw_text = clean_text(element.get_text())
        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""
        department = extract_department(raw_text)

        return {
            "institute": "IIT Kanpur",
            "network": "IIT",
            "department": department,
            "title": title,
            "position_type": normalize_position_type(title),
            "deadline": deadline,
            "detail_url": href,
            "raw_text": raw_text,
            "hash": self.generate_hash(title + href),
        }


if __name__ == "__main__":
    scraper = IITKanpurScraper()
    results = scraper.scrape()
    for item in results:
        logger.info("Found: %s | Deadline: %s", item["title"], item["deadline"])

import logging

from scrapers.utils import BaseScraper, clean_text, extract_dates, extract_department, extract_eligibility, normalize_position_type, fetch_detail_deadline

logger = logging.getLogger(__name__)


class IISERPuneScraper(BaseScraper):
    """Scraper for IISER Pune openings."""

    def __init__(self):
        super().__init__(
            institute_name="IISER Pune",
            url="https://www.iiserpune.ac.in/opportunities/openings",
            use_selenium=False,
        )

    def scrape(self):
        """Scrape research openings from IISER Pune."""
        html = self.fetch_page()
        if html is None:
            self.logger.error("Failed to fetch IISER Pune page.")
            return []

        soup = self.parse_html(html)
        if soup is None:
            return []

        openings = []
        containers = soup.select(
            "table tr, "
            "div.view-content div.views-row, "
            "ul li a, "
            "article"
        )
        for container in containers:
            record = self._parse_element(container)
            if record:
                openings.append(record)

        self.logger.info("Scraped %d openings from IISER Pune.", len(openings))
        self.save_to_json(openings)
        return openings

    def _parse_element(self, element):
        """Extract fields from a page element."""
        if element.name == "tr":
            cells = element.find_all("td")
            if len(cells) < 2:
                return None
            title = clean_text(cells[0].get_text())
        else:
            title_tag = element.find(["a", "h3", "h4", "span"])
            if title_tag is None:
                title = clean_text(element.get_text())
            else:
                title = clean_text(title_tag.get_text())

        if not title or len(title) < 5:
            return None
        if title.lower() in ("s.no", "sl.no", "#", "title", "position"):
            return None

        link_tag = element.find("a")
        detail_url = ""
        if link_tag and link_tag.get("href"):
            href = str(link_tag["href"])
            if href.startswith("/"):
                detail_url = "https://www.iiserpune.ac.in" + href
            elif href.startswith("http"):
                detail_url = href

        raw_text = clean_text(element.get_text())
        dates = extract_dates(raw_text)
        deadline = dates[-1] if dates else ""
        if not deadline and detail_url:
            deadline = fetch_detail_deadline(detail_url, session=self.session)
        department = extract_department(raw_text)
        eligibility = extract_eligibility(raw_text)

        return {
            "institute": "IISER Pune",
            "network": "IISER",
            "department": department,
            "eligibility": eligibility,
            "title": title,
            "position_type": normalize_position_type(title),
            "deadline": deadline,
            "detail_url": detail_url,
            "raw_text": raw_text,
            "hash": self.generate_hash(title + detail_url),
        }


if __name__ == "__main__":
    scraper = IISERPuneScraper()
    results = scraper.scrape()
    for item in results:
        logger.info("Found: %s | Deadline: %s", item["title"], item["deadline"])

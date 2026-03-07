import logging
import re

from scrapers.utils import BaseScraper, clean_text, extract_dates, extract_department, extract_eligibility, normalize_position_type

logger = logging.getLogger(__name__)

BASE_URL = "https://icsrstaff.iitm.ac.in/careers"
MAX_PAGES = 5


class IITMadrasScraper(BaseScraper):
    """Scraper for IIT Madras IC&SR current openings.

    The portal uses a card/div layout with h5 headings for each
    announcement and paginates via ?page=N query params.
    """

    def __init__(self):
        super().__init__(
            institute_name="IIT Madras",
            url=BASE_URL + "/current_openings.php",
            use_selenium=False,
        )

    def scrape(self):
        """Scrape project staff openings across all pages."""
        openings = []
        for page_num in range(1, MAX_PAGES + 1):
            page_url = "{}?page={}".format(self.url, page_num)
            html = self.fetch_page(url=page_url)
            if html is None:
                self.logger.warning("No response for page %d, stopping.", page_num)
                break

            soup = self.parse_html(html)
            if soup is None:
                break

            page_records = self._extract_cards(soup)
            if not page_records:
                self.logger.info("No records on page %d, stopping.", page_num)
                break

            openings.extend(page_records)
            self.logger.info("Page %d: %d records.", page_num, len(page_records))

        self.logger.info("Scraped %d openings from IIT Madras.", len(openings))
        self.save_to_json(openings)
        return openings

    def _extract_cards(self, soup):
        """Parse announcement cards from the page.

        Each card has an h5 containing the announcement title and
        sibling elements with Last Date, location, and PDF link.
        """
        records = []
        headings = soup.find_all("h5")
        for heading in headings:
            text = clean_text(heading.get_text())
            if not text or len(text) < 10:
                continue
            if "announcement" not in text.lower() and "post" not in text.lower():
                continue

            parent = heading.find_parent(["div", "li", "section"])
            if parent is None:
                parent = heading.parent

            raw_text = clean_text(parent.get_text()) if parent else text
            dates = extract_dates(raw_text)
            deadline = dates[-1] if dates else ""
            department = extract_department(raw_text)
            eligibility = extract_eligibility(raw_text)

            link_tag = parent.find("a", href=True) if parent else None
            detail_url = ""
            if link_tag:
                href = str(link_tag["href"])
                if href.startswith("/"):
                    detail_url = BASE_URL + "/" + href.lstrip("/")
                elif href.startswith("http"):
                    detail_url = href

            title = re.sub(
                r"^announcement\s+for\s+the\s+post\s+of\s+",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()
            if not title:
                title = text

            records.append({
                "institute": "IIT Madras",
                "network": "IIT",
                "department": department,
                "eligibility": eligibility,
                "title": title,
                "position_type": normalize_position_type(title),
                "deadline": deadline,
                "detail_url": detail_url,
                "raw_text": raw_text,
                "hash": self.generate_hash(title + detail_url),
            })
        return records


if __name__ == "__main__":
    scraper = IITMadrasScraper()
    results = scraper.scrape()
    for item in results:
        logger.info("Found: %s | Deadline: %s", item["title"], item["deadline"])

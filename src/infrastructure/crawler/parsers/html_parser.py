"""HTML content parser using BeautifulSoup."""

import re
from typing import Any
from urllib.parse import urljoin

from .registry import BaseParser

try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


class HTMLParser(BaseParser):
    """Parser for HTML web pages."""

    def can_parse(self, content_type: str, url: str) -> bool:
        """Check if content is HTML."""
        return "text/html" in content_type.lower()

    async def parse(self, content: str, url: str) -> dict[str, Any]:
        """Parse HTML and extract structured data."""
        if not HAS_BS4:
            return self._parse_regex(content, url)

        soup = BeautifulSoup(content, "html.parser")

        title = ""
        if soup.title:
            title = soup.title.string or ""

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)

        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            links.append({"url": href, "text": a.get_text(strip=True)})

        tables = []
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)

        return {
            "title": title,
            "text": text[:5000],
            "links": links[:100],
            "tables": tables[:10],
        }

    def _parse_regex(self, content: str, url: str) -> dict[str, Any]:
        """Fallback regex parsing when BeautifulSoup unavailable."""
        title_match = re.search(r"<title>([^<]+)</title>", content, re.IGNORECASE)
        title = title_match.group(1) if title_match else ""

        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).strip()

        links = []
        for match in re.finditer(r'href=["\']([^"\']+)["\']', content):
            href = urljoin(url, match.group(1))
            links.append({"url": href, "text": ""})

        return {
            "title": title,
            "text": text[:5000],
            "links": links[:100],
            "tables": [],
        }

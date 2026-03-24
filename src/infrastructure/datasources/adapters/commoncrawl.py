"""Common Crawl adapter - Query CDX index and extract WARC content."""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter

# CDX API base URL
CDX_API = "https://index.commoncrawl.org"

# Latest crawl indices (updated periodically)
DEFAULT_CRAWL_IDS = [
    "CC-MAIN-2026-09",
    "CC-MAIN-2026-05",
    "CC-MAIN-2025-51",
    "CC-MAIN-2025-47",
    "CC-MAIN-2025-43",
    "CC-MAIN-2025-39",
    "CC-MAIN-2025-35",
    "CC-MAIN-2025-31",
    "CC-MAIN-2025-26",
    "CC-MAIN-2025-22",
    "CC-MAIN-2025-18",
    "CC-MAIN-2025-14",
    "CC-MAIN-2025-10",
    "CC-MAIN-2025-05",
    "CC-MAIN-2024-51",
    "CC-MAIN-2024-46",
    "CC-MAIN-2024-42",
    "CC-MAIN-2024-38",
    "CC-MAIN-2024-33",
    "CC-MAIN-2024-30",
    "CC-MAIN-2024-26",
    "CC-MAIN-2024-22",
    "CC-MAIN-2024-18",
    "CC-MAIN-2024-10",
]


@dataclass
class CdxRecord:
    """A single CDX record from the Common Crawl index."""

    url: str
    timestamp: str  # YYYYMMDDHHmmss
    status: str
    mime: str
    filename: str  # WARC filename on S3
    offset: int
    length: int
    crawl_id: str

    @property
    def crawl_date(self) -> date:
        """Parse timestamp to date."""
        try:
            return datetime.strptime(self.timestamp[:8], "%Y%m%d").date()
        except (ValueError, TypeError):
            return date.today()

    @property
    def warc_url(self) -> str:
        """Full URL to download WARC record from S3."""
        return f"https://data.commoncrawl.org/{self.filename}"


@dataclass
class WebPageContent:
    """Extracted content from a WARC record."""

    url: str
    crawl_date: date
    crawl_id: str
    text: str
    content_hash: str
    content_length: int
    title: str = ""


class CommonCrawlAdapter(BaseAdapter):
    """Adapter for Common Crawl CDX Index API.

    Queries the CDX index to find archived snapshots of enterprise websites,
    then downloads and extracts text content from WARC records.

    Rate limited to 1 req/s (CDX API is sensitive to abuse).
    """

    def __init__(
        self,
        config: AdapterConfig | None = None,
        crawl_ids: list[str] | None = None,
        max_crawls: int = 12,
    ) -> None:
        if config is None:
            config = AdapterConfig(
                name="commoncrawl",
                base_url=CDX_API,
                rate_limit=1,  # 1 req/s - CDX is heavily rate limited
                cache_ttl=86400 * 7,  # 7 days - archive data doesn't change
                timeout=30.0,
            )
        super().__init__(config)
        self._crawl_ids = (crawl_ids or DEFAULT_CRAWL_IDS)[:max_crawls]
        # Separate client for WARC downloads (longer timeout)
        self._warc_client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
        )

    async def close(self) -> None:
        """Close both HTTP clients."""
        await super().close()
        await self._warc_client.aclose()

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search Common Crawl index for a URL.

        Args:
            query:
                - url: Website URL to search (required)
                - from_date: Start date (YYYY-MM-DD)
                - to_date: End date (YYYY-MM-DD)
                - limit: Max results per crawl (default 5)

        Returns:
            List of CDX records with crawl metadata.
        """
        url = query.get("url")
        if not url:
            return []

        # Clean URL for CDX query
        url = self._normalize_url(url)
        limit = query.get("limit", 5)
        from_date = query.get("from_date")
        to_date = query.get("to_date")

        all_records: list[dict[str, Any]] = []

        import asyncio as _asyncio

        for crawl_id in self._crawl_ids:
            # Optional date filtering by crawl_id
            if from_date and not self._crawl_in_range(crawl_id, from_date, to_date):
                continue

            records = await self._query_cdx(crawl_id, url, limit)
            all_records.extend(records)
            # CDX API rate limiting - 1.5s between requests
            await _asyncio.sleep(1.5)

        # Sort by date and deduplicate by month
        all_records.sort(key=lambda r: r.get("timestamp", ""))
        deduped = self._deduplicate_by_month(all_records)

        logger.info(
            f"[commoncrawl] Found {len(deduped)} snapshots for {url} "
            f"(from {len(all_records)} raw records across {len(self._crawl_ids)} crawls)"
        )
        return deduped

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get a specific CDX record and its content.

        Args:
            id: URL to look up in the most recent crawl.

        Returns:
            Most recent CDX record with extracted content, or None.
        """
        results = await self.search({"url": id, "limit": 1})
        if not results:
            return None

        # Get the most recent one
        record = results[-1]
        content = await self.fetch_content(
            CdxRecord(
                url=record["url"],
                timestamp=record["timestamp"],
                status=record["status"],
                mime=record["mime"],
                filename=record["filename"],
                offset=record["offset"],
                length=record["length"],
                crawl_id=record["crawl_id"],
            )
        )
        if content:
            record["text"] = content.text
            record["content_hash"] = content.content_hash
        return record

    async def health_check(self) -> bool:
        """Check if CDX API is reachable."""
        try:
            response = await self._client.get(
                f"{CDX_API}/collinfo.json",
                timeout=10.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def fetch_content(self, record: CdxRecord) -> WebPageContent | None:
        """Download and extract text from a WARC record.

        Args:
            record: CDX record with WARC location info.

        Returns:
            Extracted text content or None on failure.
        """
        try:
            # Download the specific byte range from the WARC file
            start = record.offset
            end = record.offset + record.length - 1
            response = await self._warc_client.get(
                record.warc_url,
                headers={"Range": f"bytes={start}-{end}"},
            )

            if response.status_code not in (200, 206):
                logger.warning(
                    f"[commoncrawl] WARC fetch failed: {response.status_code} for {record.url}"
                )
                return None

            # WARC records from CC are gzip-compressed
            raw = response.content
            try:
                import gzip

                raw = gzip.decompress(raw)
            except Exception:
                pass  # May not be compressed

            # Extract HTML from WARC response
            html = self._extract_html_from_warc(raw)
            if not html:
                return None

            # Convert HTML to clean text
            text, title = self._html_to_text(html)
            if not text or len(text) < 50:
                return None

            content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

            return WebPageContent(
                url=record.url,
                crawl_date=record.crawl_date,
                crawl_id=record.crawl_id,
                text=text,
                content_hash=content_hash,
                content_length=len(text),
                title=title,
            )

        except Exception as e:
            logger.error(f"[commoncrawl] Content extraction failed for {record.url}: {e}")
            return None

    async def get_timeline(self, url: str, months: int = 12) -> list[WebPageContent]:
        """Get monthly snapshots of a URL as a timeline.

        Args:
            url: Website URL.
            months: How many months back to look.

        Returns:
            List of WebPageContent ordered by date.
        """
        records = await self.search({"url": url, "limit": 3})
        if not records:
            return []

        timeline: list[WebPageContent] = []
        seen_hashes: set[str] = set()

        for rec_dict in records[-months:]:
            record = CdxRecord(
                url=rec_dict["url"],
                timestamp=rec_dict["timestamp"],
                status=rec_dict["status"],
                mime=rec_dict["mime"],
                filename=rec_dict["filename"],
                offset=rec_dict["offset"],
                length=rec_dict["length"],
                crawl_id=rec_dict["crawl_id"],
            )
            content = await self.fetch_content(record)
            if content:
                # Skip if content hasn't changed
                if content.content_hash in seen_hashes:
                    content.text = "[unchanged]"
                else:
                    seen_hashes.add(content.content_hash)
                timeline.append(content)

        logger.info(
            f"[commoncrawl] Timeline for {url}: {len(timeline)} snapshots, "
            f"{len(seen_hashes)} unique"
        )
        return timeline

    # --- Private methods ---

    async def _query_cdx(self, crawl_id: str, url: str, limit: int) -> list[dict[str, Any]]:
        """Query a single CDX index for a URL with retry on 503."""
        import asyncio as _asyncio
        import json

        for attempt in range(3):
            try:
                response = await self._client.get(
                    f"{CDX_API}/{crawl_id}-index",
                    params={
                        "url": url,
                        "output": "json",
                        "limit": limit,
                        "filter": "=status:200",
                        "fl": "url,timestamp,status,mime,filename,offset,length",
                    },
                    timeout=15.0,
                )

                if response.status_code == 404:
                    return []  # No results for this crawl
                if response.status_code == 503 and attempt < 2:
                    await _asyncio.sleep(3 * (attempt + 1))
                    continue
                if response.status_code != 200:
                    logger.debug(f"[commoncrawl] CDX {crawl_id} returned {response.status_code}")
                    return []

                # Parse JSON lines response (one JSON object per line, no header)
                lines = response.text.strip().split("\n")
                if not lines:
                    return []

                records = []
                for line in lines:
                    try:
                        item = json.loads(line)
                        records.append(
                            {
                                "url": item.get("url", url),
                                "timestamp": item.get("timestamp", ""),
                                "status": item.get("status", "200"),
                                "mime": item.get("mime", "text/html"),
                                "filename": item.get("filename", ""),
                                "offset": int(item.get("offset", 0)),
                                "length": int(item.get("length", 0)),
                                "crawl_id": crawl_id,
                                "source": "commoncrawl",
                            }
                        )
                    except (json.JSONDecodeError, ValueError):
                        continue

                return records

            except httpx.TimeoutException:
                logger.debug(f"[commoncrawl] CDX {crawl_id} timeout for {url}")
                if attempt < 2:
                    await _asyncio.sleep(2 * (attempt + 1))
                    continue
                return []
            except Exception as e:
                logger.debug(f"[commoncrawl] CDX {crawl_id} error: {e}")
                return []

        return []  # All retries exhausted

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for CDX query."""
        url = url.strip().lower()
        for prefix in ("https://", "http://", "www."):
            if url.startswith(prefix):
                url = url[len(prefix) :]
        # CDX works best with domain/* wildcard
        if "/" not in url:
            url = url + "/*"
        return url

    def _crawl_in_range(self, crawl_id: str, from_date: str | None, to_date: str | None) -> bool:
        """Check if a crawl ID falls within the date range."""
        # Extract year-week from crawl ID (e.g., CC-MAIN-2025-22)
        parts = crawl_id.split("-")
        if len(parts) < 4:
            return True
        try:
            year = int(parts[2])
            week = int(parts[3])
            crawl_approx = f"{year}-{week:02d}"

            if from_date:
                from_dt = datetime.strptime(from_date[:10], "%Y-%m-%d")
                from_approx = f"{from_dt.year}-{(from_dt.month * 4):02d}"
                if crawl_approx < from_approx:
                    return False
            if to_date:
                to_dt = datetime.strptime(to_date[:10], "%Y-%m-%d")
                to_approx = f"{to_dt.year}-{(to_dt.month * 4):02d}"
                if crawl_approx > to_approx:
                    return False
            return True
        except (ValueError, IndexError):
            return True

    def _deduplicate_by_month(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep only one record per month (the most recent)."""
        by_month: dict[str, dict[str, Any]] = {}
        for rec in records:
            ts = rec.get("timestamp", "")
            if len(ts) >= 6:
                month_key = ts[:6]  # YYYYMM
                by_month[month_key] = rec  # Last wins (sorted)
        return list(by_month.values())

    def _extract_html_from_warc(self, raw: bytes) -> str | None:
        """Extract HTML body from raw WARC record bytes."""
        try:
            # WARC records have: WARC header, HTTP header, then body
            # Split on double CRLF to find boundaries
            # Use bytes splitting for reliability
            sep = b"\r\n\r\n"
            parts = raw.split(sep, 2)
            if len(parts) < 3:
                # Try with just \n\n
                sep = b"\n\n"
                parts = raw.split(sep, 2)
            if len(parts) >= 3:
                body = parts[2]
                return body.decode("utf-8", errors="replace")
            return None
        except Exception:
            return None

    def _html_to_text(self, html: str) -> tuple[str, str]:
        """Convert HTML to clean text. Returns (text, title)."""
        try:
            import trafilatura

            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                favor_precision=False,
            )
            # Extract title
            title = ""
            if "<title>" in html.lower():
                start = html.lower().index("<title>") + 7
                end = html.lower().index("</title>", start)
                title = html[start:end].strip()[:200]

            return (text or "", title)
        except ImportError:
            # Fallback without trafilatura
            import re

            # Remove scripts and styles
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            # Remove tags
            text = re.sub(r"<[^>]+>", " ", text)
            # Clean whitespace
            text = re.sub(r"\s+", " ", text).strip()
            return (text, "")
        except Exception as e:
            logger.debug(f"[commoncrawl] HTML extraction error: {e}")
            return ("", "")

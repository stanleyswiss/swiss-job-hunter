"""
Scraper for LinkedIn Jobs — via the undocumented but public RSS/JSON feed.
No login required. Compliant with LinkedIn's public data access.

LinkedIn RSS endpoint:
  https://www.linkedin.com/jobs/search?keywords=...&location=...&f_TPR=r86400

Notes:
- Results are limited to ~25 jobs per request (LinkedIn-enforced)
- f_TPR=r86400 filters to last 24h; r604800 = last 7 days
- No pagination beyond what the feed returns
- If LinkedIn changes the endpoint, update _SEARCH_URL below
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import AsyncGenerator, Optional
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from scrapers.base import BaseScraper, ScrapedJob

_SEARCH_URL = "https://www.linkedin.com/jobs/search"

# Time range filter values
LAST_24H  = "r86400"
LAST_7D   = "r604800"
LAST_30D  = "r2592000"


class LinkedInRssScraper(BaseScraper):
    source_name = "linkedin.com"

    def __init__(self, time_range: str = LAST_7D) -> None:
        super().__init__()
        self.time_range = time_range

    async def scrape(
        self, keyword: str, location: str = "Zürich", max_pages: int = 1
    ) -> AsyncGenerator[ScrapedJob, None]:
        """
        Fetch LinkedIn jobs RSS feed and yield ScrapedJob instances.

        max_pages is accepted for API compatibility but LinkedIn only
        returns one page (~25 results) regardless.
        """
        params = {
            "keywords": keyword,
            "location": location,
            "f_TPR": self.time_range,
            "position": 1,
            "pageNum": 0,
        }
        url = f"{_SEARCH_URL}?{urlencode(params)}"

        try:
            resp = await self._fetch(
                url,
                headers={
                    # LinkedIn returns RSS when Accept includes application/rss+xml
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                },
            )
        except Exception as exc:
            print(f"[linkedin] fetch error: {exc}")
            return

        content_type = resp.headers.get("content-type", "")

        if "xml" in content_type or resp.text.strip().startswith("<?xml"):
            for job in self._parse_rss(resp.text):
                yield job
        else:
            # LinkedIn sometimes returns HTML (geo-block, CAPTCHA, etc.)
            print(
                "[linkedin] Warning: received non-XML response. "
                "LinkedIn may be rate-limiting or geo-blocking. "
                "Try again later or reduce scrape frequency."
            )

    def _parse_rss(self, xml_text: str) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            print(f"[linkedin] XML parse error: {exc}")
            return jobs

        # Handle both RSS 2.0 and Atom namespaces
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")

        for item in items:
            job = self._parse_item(item)
            if job:
                jobs.append(job)

        return jobs

    def _parse_item(self, item: ET.Element) -> Optional[ScrapedJob]:
        try:
            title_el = item.find("title")
            title_raw = (title_el.text or "").strip() if title_el is not None else ""

            # LinkedIn title format: "Job Title - Company Name - Location"
            # or "Job Title at Company Name"
            title, company, location = self._split_title(title_raw)

            link_el = item.find("link")
            url = (link_el.text or "").strip() if link_el is not None else ""
            # Strip tracking params — keep only the job ID part
            url = self._clean_url(url)

            desc_el = item.find("description")
            description = ""
            if desc_el is not None and desc_el.text:
                # LinkedIn descriptions are HTML — strip tags
                description = re.sub(r"<[^>]+>", " ", desc_el.text)
                description = re.sub(r"\s+", " ", description).strip()

            pub_date_el = item.find("pubDate")
            posted_at: Optional[datetime] = None
            if pub_date_el is not None and pub_date_el.text:
                try:
                    from email.utils import parsedate_to_datetime
                    posted_at = parsedate_to_datetime(pub_date_el.text.strip())
                except Exception:
                    pass

            # Job ID from guid
            guid_el = item.find("guid")
            source_id = ""
            if guid_el is not None and guid_el.text:
                # Extract numeric ID from URL like .../view/1234567890/
                m = re.search(r"/(\d{8,})", guid_el.text)
                source_id = m.group(1) if m else guid_el.text

            if not title or not url:
                return None

            return ScrapedJob(
                title=title,
                company=company,
                location=location,
                description=description,
                url=url,
                source=self.source_name,
                source_job_id=source_id,
                posted_at=posted_at,
            )

        except Exception as exc:
            print(f"[linkedin] item parse error: {exc}")
            return None

    @staticmethod
    def _split_title(raw: str) -> tuple[str, str, str]:
        """
        Parse LinkedIn RSS title into (job_title, company, location).

        Common formats:
          "Senior ML Engineer - Google - Zürich, Switzerland"
          "Senior ML Engineer at Google (Zürich)"
          "Senior ML Engineer"
        """
        # Format: "Title - Company - Location"
        if raw.count(" - ") >= 2:
            parts = raw.split(" - ", 2)
            return parts[0].strip(), parts[1].strip(), parts[2].strip()

        # Format: "Title - Company"
        if " - " in raw:
            parts = raw.split(" - ", 1)
            return parts[0].strip(), parts[1].strip(), "Switzerland"

        # Format: "Title at Company (Location)"
        m = re.match(r"^(.+?)\s+at\s+(.+?)(?:\s+\((.+?)\))?$", raw, re.IGNORECASE)
        if m:
            return m.group(1).strip(), m.group(2).strip(), (m.group(3) or "Switzerland").strip()

        return raw.strip(), "Unknown", "Switzerland"

    @staticmethod
    def _clean_url(url: str) -> str:
        """Keep only the canonical job URL, strip UTM/tracking params."""
        # LinkedIn job URLs: https://www.linkedin.com/jobs/view/1234567890/
        m = re.search(r"(https://www\.linkedin\.com/jobs/view/\d+)", url)
        if m:
            return m.group(1) + "/"
        return url

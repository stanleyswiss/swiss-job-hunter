"""
Scraper for Indeed Switzerland — uses the public RSS feed.
The Playwright approach was blocked by Indeed's bot detection.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import AsyncGenerator, Optional
from urllib.parse import urlencode, quote_plus

from scrapers.base import BaseScraper, ScrapedJob

_BASE_URL = "https://ch.indeed.com"
_RSS_URL = f"{_BASE_URL}/rss"


class IndeedChScraper(BaseScraper):
    source_name = "indeed.ch"

    async def scrape(
        self, keyword: str, location: str = "Zürich", max_pages: int = 5
    ) -> AsyncGenerator[ScrapedJob, None]:
        for page_num in range(max_pages):
            params = {
                "q": keyword,
                "l": location,
                "fromage": 30,
                "sort": "date",
                "start": page_num * 10,
            }
            url = f"{_RSS_URL}?{urlencode(params)}"
            try:
                resp = await self._fetch(url)
            except Exception as exc:
                print(f"[indeed.ch] RSS fetch error p{page_num + 1}: {exc}")
                break

            try:
                root = ET.fromstring(resp.text)
            except ET.ParseError as exc:
                print(f"[indeed.ch] XML parse error p{page_num + 1}: {exc}")
                break

            items = root.findall(".//item")
            if not items:
                break

            for item in items:
                job = self._parse_item(item)
                if job:
                    yield job

    def _parse_item(self, item: ET.Element) -> Optional[ScrapedJob]:
        try:
            title = (item.findtext("title") or "").strip()
            if not title:
                return None

            link = (item.findtext("link") or "").strip()

            # <indeed:jobkey> or extract from link
            job_key = ""
            jk_el = item.find("{com.indeed}jobkey")
            if jk_el is not None and jk_el.text:
                job_key = jk_el.text.strip()
            if not job_key and "jk=" in link:
                job_key = link.split("jk=")[-1].split("&")[0]

            # Company and location are in <source> and the description
            company = (item.findtext("source") or "").strip() or "Unknown"

            # <indeed:company> if present
            co_el = item.find("{com.indeed}company")
            if co_el is not None and co_el.text:
                company = co_el.text.strip()

            city_el = item.find("{com.indeed}city")
            state_el = item.find("{com.indeed}state")
            city = city_el.text.strip() if city_el is not None and city_el.text else ""
            state = state_el.text.strip() if state_el is not None and state_el.text else ""
            location = ", ".join(filter(None, [city, state])) or "Switzerland"

            description = ""
            desc_el = item.find("description")
            if desc_el is not None and desc_el.text:
                # Strip HTML tags from RSS snippet
                import re
                description = re.sub(r"<[^>]+>", "", desc_el.text).strip()

            salary_el = item.find("{com.indeed}salary")
            salary_raw = salary_el.text.strip() if salary_el is not None and salary_el.text else None

            return ScrapedJob(
                title=title,
                company=company,
                location=location,
                description=description,
                url=link,
                source=self.source_name,
                source_job_id=job_key or link,
                salary_raw=salary_raw,
            )
        except Exception as exc:
            print(f"[indeed.ch] parse error: {exc}")
            return None

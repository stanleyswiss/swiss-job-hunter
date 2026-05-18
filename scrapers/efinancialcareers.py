"""
Scraper for eFinancialCareers CH — finance & tech jobs in Switzerland.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import AsyncGenerator, Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, ScrapedJob

_BASE_URL = "https://www.efinancialcareers.ch"
_SEARCH_URL = f"{_BASE_URL}/en-gb/jobs"


class EFinancialCareersScraper(BaseScraper):
    source_name = "efinancialcareers.ch"

    async def scrape(
        self, keyword: str, location: str = "Zürich", max_pages: int = 5
    ) -> AsyncGenerator[ScrapedJob, None]:
        for page in range(1, max_pages + 1):
            params = {
                "keywords": keyword,
                "location": location,
                "page": page,
                "pageSize": 20,
                "sort": "date",
            }
            url = f"{_SEARCH_URL}?{urlencode(params)}"

            try:
                resp = await self._fetch(url)
            except Exception as exc:
                print(f"[efinancialcareers] page {page} error: {exc}")
                break

            soup = BeautifulSoup(resp.text, "lxml")

            # Parse JSON-LD job postings
            found = list(self._parse_json_ld(soup))
            if found:
                for job in found:
                    yield job
            else:
                cards = soup.select("[data-job-id], article.sc-bdfBwQ, div.sc-dkPtRN")
                if not cards:
                    break
                for card in cards:
                    job = self._parse_card(card)
                    if job:
                        yield job

    def _parse_json_ld(self, soup: BeautifulSoup):  # type: ignore[override]
        for script in soup.select("script[type='application/ld+json']"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "JobPosting":
                        company = (item.get("hiringOrganization") or {}).get("name", "Unknown")
                        loc = (item.get("jobLocation") or {})
                        if isinstance(loc, list):
                            loc = loc[0] if loc else {}
                        city = (loc.get("address") or {}).get("addressLocality", "Switzerland")

                        posted_at = None
                        if ts := item.get("datePosted"):
                            try:
                                posted_at = datetime.fromisoformat(ts)
                            except ValueError:
                                pass

                        yield ScrapedJob(
                            title=item.get("title", "").strip(),
                            company=company,
                            location=city,
                            description=item.get("description", ""),
                            url=item.get("url", "") or item.get("sameAs", ""),
                            source=self.source_name,
                            posted_at=posted_at,
                        )
            except Exception:
                continue

    def _parse_card(self, card) -> Optional[ScrapedJob]:  # type: ignore[return]
        try:
            title_el = card.select_one("h2, h3, [data-test='job-title']")
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            company_el = card.select_one("[data-test='company-name'], .company-name")
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            loc_el = card.select_one("[data-test='job-location'], .location")
            location = loc_el.get_text(strip=True) if loc_el else "Switzerland"
            link = card.select_one("a[href]")
            href = link["href"] if link else ""
            url = href if href.startswith("http") else f"{_BASE_URL}{href}"
            salary_el = card.select_one(".salary, [data-test='salary']")
            salary_raw = salary_el.get_text(strip=True) if salary_el else None
            return ScrapedJob(
                title=title, company=company, location=location,
                description="", url=url, source=self.source_name,
                salary_raw=salary_raw,
            )
        except Exception as exc:
            print(f"[efinancialcareers] parse error: {exc}")
            return None

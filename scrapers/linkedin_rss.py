"""
Scraper for LinkedIn Jobs — uses Playwright (public job listings, no login required).

With `LINKEDIN_COOKIE=<li_at value>` in .env, authenticated search is used which
returns up to 1000 results instead of the ~40 guest cap.
"""
from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime
from typing import AsyncGenerator, Optional, Tuple
from urllib.parse import quote_plus

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from config.settings import settings
from scrapers.base import BaseScraper, ScrapedJob

_SEARCH_URL = "https://www.linkedin.com/jobs/search"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_STEALTH = Stealth(navigator_platform_override="Win32")

# URL prefixes that indicate LinkedIn has blocked or kicked us out
_BLOCK_PATHS = ("/checkpoint/", "/authwall", "/login", "/uas/login")

LAST_24H = "r86400"
LAST_7D  = "r604800"
LAST_30D = "r2592000"

# Selectors that work for both guest (server-rendered) and logged-in (SPA) pages
_CARD_SELECTORS = [
    "div.job-search-card",       # guest HTML
    "li[data-occludable-job-id]", # logged-in SPA
    "li.jobs-search-results__list-item",  # logged-in SPA (alt)
]


class LinkedInRssScraper(BaseScraper):
    source_name = "linkedin.com"

    def __init__(self, time_range: str = LAST_7D) -> None:
        super().__init__()
        self.time_range = time_range
        self._li_at = settings.linkedin_cookie.strip()
        self._proxy = settings.linkedin_proxy.strip() or None

    @property
    def _authenticated(self) -> bool:
        return bool(self._li_at)

    async def scrape(
        self, keyword: str, location: str = "Zürich", max_pages: int = 5
    ) -> AsyncGenerator[ScrapedJob, None]:
        async with async_playwright() as pw:
            launch_args: dict = {"headless": settings.playwright_headless}
            if self._proxy:
                launch_args["proxy"] = {"server": self._proxy}
            browser = await pw.chromium.launch(**launch_args)
            context = await browser.new_context(
                user_agent=_UA,
                locale="en-US",
                viewport={"width": 1280, "height": 900},
            )
            await _STEALTH.apply_stealth_async(context)

            if self._authenticated:
                await context.add_cookies([{
                    "name": "li_at",
                    "value": self._li_at,
                    "domain": ".linkedin.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                }])

            page = await context.new_page()
            try:
                for page_num in range(max_pages):
                    url = (
                        f"{_SEARCH_URL}"
                        f"?keywords={quote_plus(keyword)}"
                        f"&location={quote_plus(location)}"
                        f"&f_TPR={self.time_range}"
                        f"&sortBy=DD"
                        f"&start={page_num * 25}"
                    )
                    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    _check_blocked(page.url)

                    # Wait for any of the known card selectors
                    cards = await self._wait_for_cards(page)
                    if not cards:
                        break

                    for card in cards:
                        job = await self._parse_card(card)
                        if job:
                            yield job

                    # Human-like: scroll through the page before moving on
                    await _human_scroll(page)

                    # Random inter-page delay (2–6s)
                    await asyncio.sleep(random.uniform(2.0, 6.0))

            finally:
                await browser.close()

    async def _wait_for_cards(self, page):
        for sel in _CARD_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=8_000)
                cards = await page.query_selector_all(sel)
                if cards:
                    return cards
            except Exception:
                continue
        return []

    async def _parse_card(self, card) -> Optional[ScrapedJob]:
        try:
            title_el = await card.query_selector("h3")
            if not title_el:
                # SPA cards use a different heading element
                title_el = await card.query_selector("[class*='title']")
            if not title_el:
                return None
            title = (await title_el.inner_text()).strip()
            if not title:
                return None

            company_el = await card.query_selector("h4") or await card.query_selector("[class*='subtitle'], [class*='company']")
            company = (await company_el.inner_text()).strip() if company_el else "Unknown"

            loc_el = await card.query_selector(".job-search-card__location") or await card.query_selector("[class*='location'], [class*='metadata']")
            location = (await loc_el.inner_text()).strip() if loc_el else "Switzerland"

            link_el = await card.query_selector("a[href*='/jobs/view/']")
            href = (await link_el.get_attribute("href") or "") if link_el else ""
            m = re.search(r"/jobs/view/[^/]+-(\d+)", href)
            job_id = m.group(1) if m else href
            url = f"https://www.linkedin.com/jobs/view/{job_id}/" if job_id.isdigit() else href

            time_el = await card.query_selector("time")
            posted_at = None
            if time_el:
                dt = await time_el.get_attribute("datetime")
                try:
                    posted_at = datetime.fromisoformat(dt) if dt else None
                except (ValueError, TypeError):
                    pass

            return ScrapedJob(
                title=title,
                company=company,
                location=location,
                description="",
                url=url,
                source=self.source_name,
                source_job_id=job_id,
                posted_at=posted_at,
            )
        except Exception as exc:
            print(f"[linkedin] parse error: {exc}")
            return None

    async def fetch_full_description(self, job_url: str) -> Optional[Tuple[str, str]]:
        """Fetch full description via LinkedIn's public guest job API."""
        from bs4 import BeautifulSoup

        m = re.search(r"(\d{6,})", job_url)
        if not m:
            return None
        job_id = m.group(1)

        api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
        canonical = f"https://www.linkedin.com/jobs/view/{job_id}/"
        try:
            resp = await self._fetch(api_url)
            if resp.status_code == 404:
                return ()  # type: ignore
            soup = BeautifulSoup(resp.text, "lxml")

            el = soup.select_one(".show-more-less-html__markup")
            if not el:
                el = soup.select_one(".description__text")
            if el:
                text = el.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return text, canonical

            return None
        except Exception as exc:
            print(f"[linkedin] detail fetch error for {job_id}: {exc}")
            return None


class LinkedInBlockedError(RuntimeError):
    """Raised when LinkedIn redirects to a checkpoint, authwall, or login page."""


def _check_blocked(current_url: str) -> None:
    from urllib.parse import urlparse
    path = urlparse(current_url).path
    if any(path.startswith(p) for p in _BLOCK_PATHS):
        hint = (
            "IP blocked — try switching LINKEDIN_PROXY in .env, "
            "or wait 24-48h for the block to lift."
            if not settings.linkedin_cookie
            else
            "Cookie expired or account restricted — re-paste li_at from your browser. "
            "If the problem persists, your IP may also be blocked; set LINKEDIN_PROXY."
        )
        raise LinkedInBlockedError(f"LinkedIn redirected to {current_url!r}. {hint}")


async def _human_scroll(page) -> None:
    """Scroll down the page in a few steps to simulate reading."""
    viewport_height = 900
    scroll_steps = random.randint(3, 6)
    for _ in range(scroll_steps):
        delta = random.randint(300, viewport_height)
        await page.mouse.wheel(0, delta)
        await asyncio.sleep(random.uniform(0.3, 0.9))

"""
Web form application module — uses Playwright to fill and submit job forms.
Currently supports: jobs.ch

IMPORTANT: Always runs in dry_run=True by default.
The user must explicitly confirm before any form is submitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright

from config.settings import settings
from db.models import Job


@dataclass
class ApplicantInfo:
    """Personal info for form filling (no sensitive data stored here)."""
    first_name: str
    last_name: str
    email: str
    phone: str
    cover_letter: str
    cv_pdf_path: Path
    linkedin_url: str = ""
    github_url: str = ""


async def apply_jobs_ch(
    job: Job,
    info: ApplicantInfo,
    dry_run: bool = True,
) -> bool:
    """
    Fill the jobs.ch application form for a given job.

    Steps:
    1. Navigate to the job URL
    2. Click "Apply Now" / "Jetzt bewerben"
    3. Fill in personal info fields
    4. Upload CV
    5. Paste cover letter
    6. (dry_run=False only) Submit

    Returns True if successful (or would be, in dry_run mode).
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=settings.playwright_headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            print(f"[form] Navigating to {job.url}")
            await page.goto(job.url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(2000)

            # Click apply button
            apply_btn = await page.query_selector(
                "button:has-text('Apply'), "
                "a:has-text('Apply Now'), "
                "button:has-text('Bewerben'), "
                "a:has-text('Jetzt bewerben')"
            )
            if not apply_btn:
                print("[form] Could not find Apply button — manual application needed")
                return False

            if dry_run:
                print(f"[DRY RUN] Would click Apply and fill form for: {job.title} @ {job.company}")
                print(f"  Name: {info.first_name} {info.last_name}")
                print(f"  Email: {info.email}")
                print(f"  CV: {info.cv_pdf_path}")
                return True

            await apply_btn.click()
            await page.wait_for_timeout(2000)

            # Fill common form fields
            await _try_fill(page, "[name='firstName'], #firstName, [placeholder*='First']", info.first_name)
            await _try_fill(page, "[name='lastName'], #lastName, [placeholder*='Last']", info.last_name)
            await _try_fill(page, "[name='email'], #email, [type='email']", info.email)
            await _try_fill(page, "[name='phone'], #phone, [type='tel']", info.phone)

            # Cover letter textarea
            await _try_fill(
                page,
                "textarea[name*='cover'], textarea[name*='letter'], textarea[placeholder*='cover']",
                info.cover_letter,
            )

            # CV upload
            file_input = await page.query_selector("input[type='file']")
            if file_input and info.cv_pdf_path.exists():
                await file_input.set_input_files(str(info.cv_pdf_path))
                print(f"[form] CV uploaded: {info.cv_pdf_path.name}")

            # DO NOT SUBMIT — user must confirm
            print("[form] Form filled. Review in browser before submitting manually.")
            print("       (Set dry_run=False and call page.click('button[type=submit]') to auto-submit)")

            # Keep browser open for review
            await page.wait_for_timeout(10_000)
            return True

        except Exception as exc:
            print(f"[form] Error: {exc}")
            return False
        finally:
            await browser.close()


async def _try_fill(page, selector: str, value: str) -> None:
    """Try multiple selectors, fill the first one found."""
    for sel in selector.split(", "):
        el = await page.query_selector(sel.strip())
        if el:
            await el.fill(value)
            return

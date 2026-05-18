"""Tests for scrapers — uses mocked HTTP responses."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_jobs_ch_scraper_parse():
    from scrapers.jobs_ch import JobsChScraper

    mock_response = {
        "documents": [
            {
                "id": "12345",
                "title": "Senior ML Engineer",
                "company": {"name": "Acme AG"},
                "place": {"name": "Zürich"},
                "canton": {"name": "ZH"},
                "teaser": "Join our AI team...",
                "slug": "senior-ml-engineer-acme",
                "publication_date": "2025-01-15T08:00:00Z",
                "salary": {"min": 120000, "max": 160000},
                "workload": [{"min": 80, "max": 100}],
            }
        ],
        "num_hits": 1,
    }

    scraper = JobsChScraper()
    job = scraper._parse_document(mock_response["documents"][0])

    assert job is not None
    assert job.title == "Senior ML Engineer"
    assert job.company == "Acme AG"
    assert "Zürich" in job.location
    assert "120,000" in (job.salary_raw or "")
    assert job.source_job_id == "12345"


@pytest.mark.asyncio
async def test_jobup_ch_scraper_parse():
    from scrapers.jobup_ch import JobupChScraper

    doc = {
        "id": "99",
        "title": "Data Scientist",
        "company": {"name": "Swiss Bank"},
        "place": {"name": "Genève"},
        "teaser": "Exciting data science role",
        "slug": "data-scientist-swiss-bank",
        "publication_date": "2025-02-01T09:00:00Z",
    }

    scraper = JobupChScraper()
    job = scraper._parse(doc)

    assert job is not None
    assert job.title == "Data Scientist"
    assert job.company == "Swiss Bank"
    assert job.source == "jobup.ch"

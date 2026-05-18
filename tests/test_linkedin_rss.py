"""Tests for LinkedIn RSS scraper — no network calls."""
import pytest
from scrapers.linkedin_rss import LinkedInRssScraper

RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>LinkedIn Jobs</title>
    <item>
      <title>Senior ML Engineer - Google - Zürich, Switzerland</title>
      <link>https://www.linkedin.com/jobs/view/1234567890/?trk=rss</link>
      <guid>https://www.linkedin.com/jobs/view/1234567890/</guid>
      <pubDate>Mon, 06 Jan 2025 10:00:00 +0000</pubDate>
      <description>&lt;p&gt;Join our AI team in Zürich.&lt;/p&gt;</description>
    </item>
    <item>
      <title>Data Scientist at Swiss Re (Zürich)</title>
      <link>https://www.linkedin.com/jobs/view/9876543210/?trk=rss</link>
      <guid>https://www.linkedin.com/jobs/view/9876543210/</guid>
      <pubDate>Tue, 07 Jan 2025 09:00:00 +0000</pubDate>
      <description>&lt;p&gt;Exciting data science role.&lt;/p&gt;</description>
    </item>
  </channel>
</rss>"""


def test_split_title_dash_format():
    s = LinkedInRssScraper()
    title, company, location = s._split_title("Senior ML Engineer - Google - Zürich, Switzerland")
    assert title == "Senior ML Engineer"
    assert company == "Google"
    assert location == "Zürich, Switzerland"


def test_split_title_at_format():
    s = LinkedInRssScraper()
    title, company, location = s._split_title("Data Scientist at Swiss Re (Zürich)")
    assert title == "Data Scientist"
    assert company == "Swiss Re"
    assert location == "Zürich"


def test_split_title_no_company():
    s = LinkedInRssScraper()
    title, company, location = s._split_title("ML Engineer")
    assert title == "ML Engineer"
    assert company == "Unknown"
    assert location == "Switzerland"


def test_clean_url_strips_tracking():
    url = "https://www.linkedin.com/jobs/view/1234567890/?trk=rss&refId=abc123"
    cleaned = LinkedInRssScraper._clean_url(url)
    assert cleaned == "https://www.linkedin.com/jobs/view/1234567890/"
    assert "trk" not in cleaned


def test_parse_rss_full():
    s = LinkedInRssScraper()
    jobs = s._parse_rss(RSS_SAMPLE)
    assert len(jobs) == 2

    j0 = jobs[0]
    assert j0.title == "Senior ML Engineer"
    assert j0.company == "Google"
    assert "Zürich" in j0.location
    assert j0.source == "linkedin.com"
    assert j0.source_job_id == "1234567890"
    assert j0.url == "https://www.linkedin.com/jobs/view/1234567890/"
    assert "Zürich" in j0.description

    j1 = jobs[1]
    assert j1.title == "Data Scientist"
    assert j1.company == "Swiss Re"
    assert j1.source_job_id == "9876543210"

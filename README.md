<div align="center">

# 🇨🇭 Swiss Job Hunter

**Automated job search, deduplication, scoring, and application tracking for Switzerland**

[![CI](https://github.com/Donvink/swiss-job-hunter/actions/workflows/ci.yml/badge.svg)](https://github.com/Donvink/swiss-job-hunter/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Features](#features) · [Quick Start](#quick-start) · [UI](#ui) · [CLI](#cli) · [Architecture](#architecture)

![Swiss Job Hunter UI](docs/screenshot.png)

</div>

---

## Why

Job searching in Switzerland is fragmented — the same listing appears on jobs.ch, Indeed, LinkedIn, and three other platforms simultaneously. You end up manually deduplicating, copy-pasting cover letters, and losing track of what you applied to.

Swiss Job Hunter automates the boring parts:
- Scrapes 7 Swiss job boards, deduplicates across sources
- Scores each job against your CV (keyword + LLM)
- Generates tailored cover letters via Claude / DeepSeek
- Tracks every application with a Kanban board and timeline

Built by a Senior ML/Perception Engineer relocating to Zürich on a B permit.

---

## Features

| | Feature |
|---|---|
| ⬇ | **Multi-source scraping** — jobs.ch, SwissDevJobs, Indeed CH, jobup.ch, Züri.Jobs, eFinancialCareers, LinkedIn RSS |
| 🔁 | **Smart deduplication** — SHA-256 exact match + MiniLM semantic similarity |
| 📄 | **Full JD enrichment** — fetches complete job descriptions beyond preview snippets |
| ⭐ | **CV matching** — weighted keyword scoring + LLM deep analysis (Claude / DeepSeek) |
| ✍ | **Cover letter generation** — personalized EN/DE letters via Claude API |
| 📋 | **Kanban tracker** — Viewed → Applied → Interview → Offer pipeline |
| 🕐 | **Timeline** — per-job event log (recruiter call, interviews, offer, rejection) |
| 🌐 | **Web UI** — React dashboard + FastAPI backend |
| ⌨ | **CLI** — full terminal interface for power users |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Anthropic API key](https://console.anthropic.com) and/or [DeepSeek API key](https://platform.deepseek.com)

### 1. Clone & install

```bash
git clone https://github.com/Donvink/swiss-job-hunter.git
cd swiss-job-hunter

# Python dependencies
pip install -r requirements.txt
playwright install chromium

# Frontend dependencies
cd ui && npm install && cd ..
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` — at minimum set your API key:

```bash
ANTHROPIC_API_KEY=sk-ant-...   # Claude API
# or
DEEPSEEK_API_KEY=sk-...        # DeepSeek (cheaper)
LLM_PROVIDER=auto              # auto = round-robin between configured providers
```

### 3. Add your CV

```bash
# Copy your CV as plain text
cp your_cv.txt data/cv.txt
```

### 4. Start

```bash
# Terminal 1 — backend
python server.py

# Terminal 2 — frontend
cd ui && npm run dev
```

Open **http://localhost:5173**

---

## UI

The web dashboard guides you through the full pipeline:

```
① SEARCH  →  ② ENRICH  →  ③ SCORE  →  ④ COVER LETTER  →  ⑤ APPLY  →  ⑥ TRACK
```

**BOARD** — Browse and filter all jobs, auto-marks as Viewed when opened

**TRACKER** — Kanban board showing your active applications across all stages

**TIMELINE** — Per-job event log to track every interaction

---

## CLI

```bash
# Scrape jobs
sjh search "perception engineer" --location "Zürich" --source jobs.ch

# Enrich with full descriptions
sjh enrich --source jobs.ch

# Score against your CV
sjh analyze                    # keyword scoring (fast)
sjh analyze --llm              # LLM scoring (accurate)

# View top matches
sjh top --limit 20

# Generate cover letter
sjh cover <job_id> --lang en

# Daily summary
sjh digest
```

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   scrapers/ │────▶│  dedup/      │────▶│  db/        │
│  7 sources  │     │  exact +     │     │  SQLite     │
│  httpx +    │     │  semantic    │     │  jobs.db    │
│  playwright │     └──────────────┘     └──────┬──────┘
└─────────────┘                                 │
                                                ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  ui/        │◀───▶│  server.py   │────▶│  analyzer/  │
│  React +    │     │  FastAPI     │     │  scorer.py  │
│  Vite       │     │  SSE stream  │     │  keyword +  │
└─────────────┘     └──────────────┘     │  LLM        │
                                         └──────┬──────┘
                                                │
                                         ┌──────▼──────┐
                                         │  llm/       │
                                         │  router.py  │
                                         │  Claude /   │
                                         │  DeepSeek   │
                                         └─────────────┘
```

### Tech Stack

| Layer | Tech |
|---|---|
| Scraping | `httpx`, `playwright`, `beautifulsoup4` |
| Dedup | SHA-256 + `sentence-transformers` (MiniLM) |
| Storage | SQLite + SQLAlchemy 2.x |
| LLM | Anthropic Claude + DeepSeek (OpenAI-compatible) |
| Backend | FastAPI + SSE streaming |
| Frontend | React 18 + Vite |
| CLI | Typer + Rich |

---

## Supported Job Boards

| Source | Method | Notes |
|---|---|---|
| jobs.ch | JSON API + HTML detail | Primary Swiss board |
| jobup.ch | JSON API | French-speaking Switzerland |
| SwissDevJobs | HTML / BS4 | IT/software focused |
| Indeed CH | Playwright | JS-rendered, anti-bot |
| Züri.Jobs | JSON-LD + HTML | Zürich-focused |
| eFinancialCareers | JSON-LD + HTML | Finance & tech |
| LinkedIn | RSS feed | Public feed, no login |

---

## Adding a New Job Board

1. Create `scrapers/my_board.py` extending `BaseScraper`
2. Implement `source_name` property and `scrape()` async generator
3. Register in `scrapers/__init__.py` → `SCRAPER_REGISTRY`

```python
class MyBoardScraper(BaseScraper):
    source_name = "myboard.ch"

    async def scrape(self, keyword, location, max_pages):
        # yield ScrapedJob instances
        ...
```

---

## WSL / Windows Notes

If running on WSL with Windows browser, add to `~/.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
```

Then `wsl --shutdown` and restart.

---

## Responsible Scraping

- Random delays between requests (1.5–4s)
- Retry with exponential backoff
- Respects rate limits — do not set `SCRAPER_DELAY_MIN` below 1.0

---

## License

MIT © [Leo Zhong](https://github.com/Donvink)

---

<div align="center">
<sub>Built in Zürich · Swiss B Permit holder · Open to collaborations</sub>
</div>

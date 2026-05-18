"""
Analysis reports — daily digest, top matches, trend summaries.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from rich.console import Console
from rich.table import Table
from sqlalchemy import func

from db.models import Job, JobStatus
from db.session import get_session

console = Console()


def print_top_matches(limit: int = 20, min_score: float = 0.0) -> None:
    """Print top matching jobs ranked by match score."""
    with get_session() as session:
        jobs = (
            session.query(Job)
            .filter(Job.match_score >= min_score)
            .filter(Job.status.in_([JobStatus.NEW, JobStatus.ANALYZED, JobStatus.SHORTLISTED]))
            .order_by(Job.match_score.desc())
            .limit(limit)
            .all()
        )

    table = Table(title=f"Top {limit} Job Matches", show_lines=True)
    table.add_column("Score", style="bold green", width=6)
    table.add_column("Title", style="bold white", width=40)
    table.add_column("Company", width=25)
    table.add_column("Location", width=15)
    table.add_column("Source", style="dim", width=15)
    table.add_column("Status", width=12)

    for job in jobs:
        score_str = f"{job.match_score:.0%}" if job.match_score else "—"
        table.add_row(
            score_str,
            job.title[:40],
            job.company[:25],
            job.location[:15],
            job.source,
            job.status,
        )

    console.print(table)


def daily_digest() -> None:
    """Summary of today's scraped jobs."""
    since = datetime.utcnow() - timedelta(hours=24)
    with get_session() as session:
        total = session.query(func.count(Job.id)).filter(Job.scraped_at >= since).scalar()
        by_source = (
            session.query(Job.source, func.count(Job.id))
            .filter(Job.scraped_at >= since)
            .group_by(Job.source)
            .all()
        )
        shortlisted = (
            session.query(func.count(Job.id))
            .filter(Job.scraped_at >= since, Job.status == JobStatus.SHORTLISTED)
            .scalar()
        )

    console.print(f"\n[bold]Daily Digest[/bold] — {datetime.now().strftime('%Y-%m-%d')}")
    console.print(f"  New jobs scraped:  [green]{total}[/green]")
    console.print(f"  Shortlisted:       [yellow]{shortlisted}[/yellow]")
    console.print("\n  By source:")
    for source, count in sorted(by_source, key=lambda x: -x[1]):
        console.print(f"    {source:<25} {count}")
    console.print()


def pipeline_summary() -> None:
    """Show counts per pipeline status."""
    with get_session() as session:
        rows = (
            session.query(Job.status, func.count(Job.id))
            .group_by(Job.status)
            .all()
        )

    table = Table(title="Pipeline Summary")
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")

    status_order = [s.value for s in JobStatus]
    row_map = {r[0]: r[1] for r in rows}
    for status in status_order:
        count = row_map.get(status, 0)
        color = {
            "new": "white", "analyzed": "cyan", "shortlisted": "yellow",
            "applied": "green", "interviewing": "bold green",
            "offer": "bold magenta", "rejected": "red", "archived": "dim",
        }.get(status, "white")
        table.add_row(f"[{color}]{status}[/{color}]", str(count))

    console.print(table)

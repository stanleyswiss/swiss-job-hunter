"""
Quick DB inspection — run directly to see what's in the database.
Usage: python tools/inspect_db.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.session import get_session, init_db
from db.models import Job, RawJob, JobStatus
from sqlalchemy import func

init_db()

with get_session() as session:
    total = session.query(func.count(Job.id)).scalar()
    print(f"\n{'='*60}")
    print(f"  Total jobs in DB: {total}")
    print(f"{'='*60}")

    if total == 0:
        print("  (empty — nothing scraped yet)")
        sys.exit(0)

    # By source
    print("\n📊 By source:")
    rows = session.query(Job.source, func.count(Job.id)).group_by(Job.source).all()
    for source, count in sorted(rows, key=lambda x: -x[1]):
        print(f"   {source:<30} {count:>4} jobs")

    # By status
    print("\n📋 By status:")
    rows = session.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
    for status, count in rows:
        print(f"   {status:<20} {count:>4}")

    # Latest 10 jobs
    print("\n🆕 Latest 10 jobs:")
    print(f"   {'ID':<5} {'Title':<45} {'Company':<25} {'Location':<15} {'Type':<10}")
    print("   " + "-"*105)
    jobs = session.query(Job).order_by(Job.scraped_at.desc()).limit(10).all()
    for j in jobs:
        title = (j.title or "")[:44]
        company = (j.company or "")[:24]
        location = (j.location or "")[:14]
        etype = (j.employment_type or "—")[:9]
        print(f"   {j.id:<5} {title:<45} {company:<25} {location:<15} {etype:<10}")

    # Raw records
    raw_total = session.query(func.count(RawJob.id)).scalar()
    print(f"\n🗃  Raw records: {raw_total}")

    # Sample one full job
    print("\n🔍 Sample job (most recent):")
    j = session.query(Job).order_by(Job.scraped_at.desc()).first()
    if j:
        print(f"   Title:       {j.title}")
        print(f"   Company:     {j.company}")
        print(f"   Location:    {j.location}")
        print(f"   Type:        {j.employment_type}")
        print(f"   Source:      {j.source}")
        print(f"   URL:         {j.url}")
        print(f"   Posted:      {j.posted_at}")
        print(f"   Scraped:     {j.scraped_at}")
        print(f"   Description: {(j.description or '')[:200]}...")
    print()

"""JobSpy integration for LinkedIn + Indeed job collection."""

import uuid
from datetime import datetime

from jobspy import scrape_jobs

from tycho.collector.base import BaseCollector
from tycho.models import Job, JobStatus


class JobSpyCollector(BaseCollector):
    """Collect jobs from LinkedIn and Indeed via JobSpy."""

    def __init__(self, sources: list[str] | None = None, country: str = "Spain"):
        self.sources = sources or ["indeed", "linkedin"]
        self.country = country

    def collect(
        self,
        search_terms: list[str],
        locations: list[str],
        results_wanted: int = 50,
    ) -> list[Job]:
        """Collect jobs for all (term, location) combinations."""
        all_jobs: list[Job] = []

        for term in search_terms:
            for location in locations:
                try:
                    jobs = self._scrape(term, location, results_wanted)
                    all_jobs.extend(jobs)
                except Exception as e:
                    print(f"  [warning] Failed to scrape '{term}' in '{location}': {e}")

        return all_jobs

    def _scrape(self, term: str, location: str, results_wanted: int) -> list[Job]:
        """Scrape jobs for a single (term, location) pair."""
        df = scrape_jobs(
            site_name=self.sources,
            search_term=term,
            location=location,
            results_wanted=results_wanted,
            country_indeed=self.country,
        )

        jobs = []
        for _, row in df.iterrows():
            job = Job(
                id=str(uuid.uuid4()),
                source=str(row.get("site", "unknown")),
                source_id=str(row.get("id", "")),
                title=str(row.get("title", "")),
                company=str(row.get("company", "")),
                location=str(row.get("location", "")),
                description=str(row.get("description", "")),
                url=str(row.get("job_url", "")),
                salary_min=_parse_float(row.get("min_amount")),
                salary_max=_parse_float(row.get("max_amount")),
                date_posted=_parse_date(row.get("date_posted")),
                date_collected=datetime.now(),
                status=JobStatus.NEW,
            )
            jobs.append(job)

        return jobs


def _parse_float(val) -> float | None:
    """Safely parse a float value."""
    if val is None:
        return None
    try:
        import math
        f = float(val)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _parse_date(val) -> datetime | None:
    """Safely parse a date value."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        import pandas as pd
        if pd.isna(val):
            return None
        return datetime.fromisoformat(str(val))
    except (ValueError, TypeError, ImportError):
        return None

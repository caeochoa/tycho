"""JobSpy integration for LinkedIn + Indeed job collection."""

import uuid
from datetime import datetime, timedelta

from jobspy import scrape_jobs
from jobspy.linkedin import LinkedIn
from jobspy.model import Country, Location

from tycho.collector.base import BaseCollector
from tycho.collector.parsing import (
    parse_date as _parse_date,
    parse_float as _parse_float,
    parse_str as _parse_str,
)
from tycho.models import Job, JobStatus


def _patch_linkedin_get_location():
    """
    Monkey-patch LinkedIn._get_location to gracefully handle country strings
    that are not in jobspy's Country enum (e.g. 'Sri Lanka', 'Kosovo').

    Without this patch, a single job listing whose scraped location contains
    an unrecognised country name raises a ValueError that aborts the entire
    (term, location) scrape batch.
    """
    _original_get_location = LinkedIn._get_location

    def _safe_get_location(self, metadata_card):
        try:
            return _original_get_location(self, metadata_card)
        except (ValueError, Exception):
            # Fall back to the configured scrape country so the job is still
            # collected, just without a parsed country on its location.
            try:
                return Location(country=Country.from_string(self.country))
            except Exception:
                return Location()

    LinkedIn._get_location = _safe_get_location


_patch_linkedin_get_location()


class JobSpyCollector(BaseCollector):
    """Collect jobs from LinkedIn and Indeed via JobSpy."""

    def __init__(
        self,
        sources: list[str] | None = None,
        country: str = "Spain",
        location_countries: dict[str, str] | None = None,
        linkedin_fetch_description: bool = True,
        max_age_days: int | None = None,
    ):
        self.sources = sources or ["indeed", "linkedin"]
        self.country = country
        self.location_countries = location_countries or {}
        self.linkedin_fetch_description = linkedin_fetch_description
        self.max_age_days = max_age_days or None  # 0 disables like None

    def collect(
        self,
        search_terms: list[str],
        locations: list[str],
        results_wanted: int = 50,
    ) -> list[Job]:
        """Collect jobs for all (term, location) combinations."""
        all_jobs: list[Job] = []

        missing = sorted(
            {loc for loc in locations if loc != "Remote"} - set(self.location_countries)
        )
        for loc in missing:
            print(
                f"  [warning] '{loc}' has no entry in search.location_countries; "
                f"falling back to search.country ('{self.country}') for its Indeed locale. "
                f"Add '{loc}: \"<its country>\"' to config.yaml's search.location_countries "
                f"to pin it."
            )

        for term in search_terms:
            for location in locations:
                country = self.location_countries.get(location, self.country)
                try:
                    jobs = self._scrape(term, location, results_wanted, country)
                    all_jobs.extend(jobs)
                except Exception as e:
                    print(f"  [warning] Failed to scrape '{term}' in '{location}': {e}")

        return all_jobs

    def _scrape(
        self, term: str, location: str, results_wanted: int, country: str
    ) -> list[Job]:
        """Scrape jobs for a single (term, location) pair."""
        kwargs = {}
        if self.max_age_days:
            kwargs["hours_old"] = self.max_age_days * 24

        df = scrape_jobs(
            site_name=self.sources,
            search_term=term,
            location=location,
            results_wanted=results_wanted,
            country_indeed=country,
            linkedin_fetch_description=self.linkedin_fetch_description,
            **kwargs,
        )

        # hours_old is best-effort per site (LinkedIn still leaks old postings),
        # so also drop anything whose parsed date is past the cutoff.
        cutoff = (
            datetime.now() - timedelta(days=self.max_age_days)
            if self.max_age_days
            else None
        )

        jobs = []
        for _, row in df.iterrows():
            job = Job(
                id=str(uuid.uuid4()),
                source=_parse_str(row.get("site")) or "unknown",
                source_id=_parse_str(row.get("id")),
                title=_parse_str(row.get("title")),
                company=_parse_str(row.get("company")),
                location=_parse_str(row.get("location")),
                description=_parse_str(row.get("description")),
                url=_parse_str(row.get("job_url")),
                salary_min=_parse_float(row.get("min_amount")),
                salary_max=_parse_float(row.get("max_amount")),
                salary_currency=_parse_str(row.get("currency")) or None,
                salary_interval=_parse_str(row.get("interval")) or None,
                date_posted=_parse_date(row.get("date_posted")),
                date_collected=datetime.now(),
                status=JobStatus.NEW,
            )
            if cutoff and job.date_posted and job.date_posted < cutoff:
                continue
            jobs.append(job)

        return jobs

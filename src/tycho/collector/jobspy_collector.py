"""JobSpy integration for LinkedIn + Indeed job collection."""

import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from jobspy import scrape_jobs
from jobspy.linkedin import LinkedIn
from jobspy.model import Country, Location, ScraperInput, Site

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
        except ValueError:
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
        known_ids: "dict[str, set[str]] | None" = None,
    ):
        self.sources = sources or ["indeed", "linkedin"]
        self.country = country
        self.location_countries = location_countries or {}
        self.linkedin_fetch_description = linkedin_fetch_description
        self.max_age_days = max_age_days or None  # 0 disables like None
        # source -> source_ids already stored. When given, LinkedIn descriptions
        # are fetched only for jobs not in this map (and not seen earlier in
        # this run); known LinkedIn jobs are dropped without any extra request.
        self.known_ids = known_ids
        self._seen_linkedin: set[str] = set()
        self._linkedin_detail: LinkedIn | None = None
        # per-term stats for the end-of-run summary: term -> [returned, known]
        self.term_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])

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
                started = time.monotonic()
                try:
                    jobs = self._scrape(term, location, results_wanted, country)
                    all_jobs.extend(jobs)
                except Exception as e:
                    print(f"  [warning] Failed to scrape '{term}' in '{location}': {e}")
                    continue
                print(
                    f"  [search] '{term}' / {location}: "
                    f"{time.monotonic() - started:.1f}s, kept {len(jobs)}"
                )

        self._print_term_summary()
        return all_jobs

    def _print_term_summary(self) -> None:
        """Per-term share of results already in the DB (trim candidates)."""
        if not self.known_ids or not self.term_stats:
            return
        print("  [summary] term: returned, already known")
        for term, (returned, known) in self.term_stats.items():
            pct = 100 * known / returned if returned else 0
            print(f"    {term}: {returned} returned, {known} known ({pct:.0f}%)")

    def _skip_linkedin_details(self) -> bool:
        return bool(
            self.known_ids is not None
            and self.linkedin_fetch_description
            and "linkedin" in self.sources
        )

    def _fetch_linkedin_description(self, source_id: str) -> str:
        """Fetch one LinkedIn description via jobspy's (private) detail call."""
        if self._linkedin_detail is None:
            detail = LinkedIn()
            detail.scraper_input = ScraperInput(site_type=[Site.LINKEDIN])
            self._linkedin_detail = detail
        job_id = source_id.removeprefix("li-")
        return self._linkedin_detail._get_job_details(job_id).get("description") or ""

    def _scrape(
        self, term: str, location: str, results_wanted: int, country: str
    ) -> list[Job]:
        """Scrape jobs for a single (term, location) pair."""
        kwargs = {}
        if self.max_age_days:
            kwargs["hours_old"] = self.max_age_days * 24

        lazy = self._skip_linkedin_details()
        scrape_started = time.monotonic()
        df = scrape_jobs(
            site_name=self.sources,
            search_term=term,
            location=location,
            results_wanted=results_wanted,
            country_indeed=country,
            # Lazy mode: cards only; descriptions are fetched below for new jobs.
            linkedin_fetch_description=self.linkedin_fetch_description and not lazy,
            **kwargs,
        )
        scrape_secs = time.monotonic() - scrape_started

        # hours_old is best-effort per site (LinkedIn still leaks old postings),
        # so also drop anything whose parsed date is past the cutoff.
        cutoff = (
            datetime.now() - timedelta(days=self.max_age_days)
            if self.max_age_days
            else None
        )

        per_site: dict[str, int] = defaultdict(int)
        known_total = 0
        fetched = 0
        fetch_secs = 0.0
        jobs = []
        for _, row in df.iterrows():
            site = _parse_str(row.get("site")) or "unknown"
            sid = _parse_str(row.get("id"))
            per_site[site] += 1
            is_known = bool(self.known_ids and sid in self.known_ids.get(site, ()))
            known_total += is_known
            description = _parse_str(row.get("description"))
            if lazy and site == "linkedin":
                # Known (in DB) or already handled this run: drop. Keeping it
                # would let upsert_job overwrite the stored description with "".
                if is_known or sid in self._seen_linkedin:
                    continue
                self._seen_linkedin.add(sid)
                t0 = time.monotonic()
                try:
                    description = self._fetch_linkedin_description(sid)
                except Exception as e:
                    print(f"  [warning] LinkedIn description fetch failed for {sid}: {e}")
                    description = ""
                fetch_secs += time.monotonic() - t0
                fetched += 1
            job = Job(
                id=str(uuid.uuid4()),
                source=site,
                source_id=sid,
                title=_parse_str(row.get("title")),
                company=_parse_str(row.get("company")),
                location=_parse_str(row.get("location")),
                description=description,
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

        self.term_stats[term][0] += len(df)
        self.term_stats[term][1] += known_total
        print(
            f"  [scrape] '{term}' / {location}: scrape_jobs {scrape_secs:.1f}s, "
            f"returned {dict(per_site)}, already in DB {known_total}"
            + (f", fetched {fetched} descriptions in {fetch_secs:.1f}s" if lazy else "")
        )
        return jobs

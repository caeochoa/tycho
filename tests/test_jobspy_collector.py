"""Tests for the JobSpy collector's row → Job mapping."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd

from tycho.collector.jobspy_collector import JobSpyCollector


def _fake_df(**overrides):
    row = {
        "site": "indeed",
        "id": "in-123",
        "title": "ML Engineer",
        "company": "Acme",
        "location": "Madrid, Spain",
        "description": "Do ML things",
        "job_url": "https://example.com/job",
        "min_amount": 50000.0,
        "max_amount": 70000.0,
        "currency": "EUR",
        "interval": "yearly",
        "date_posted": "2026-07-01",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def _collect_one(df):
    collector = JobSpyCollector()
    with patch("tycho.collector.jobspy_collector.scrape_jobs", return_value=df):
        jobs = collector.collect(search_terms=["ml"], locations=["Madrid"])
    assert len(jobs) == 1
    return jobs[0]


class TestSalaryMetadataMapping:
    def test_currency_and_interval_mapped(self):
        job = _collect_one(_fake_df())
        assert job.salary_min == 50000.0
        assert job.salary_max == 70000.0
        assert job.salary_currency == "EUR"
        assert job.salary_interval == "yearly"

    def test_missing_currency_and_interval_are_none(self):
        job = _collect_one(_fake_df(currency=None, interval=None))
        assert job.salary_currency is None
        assert job.salary_interval is None

    def test_nan_currency_is_none(self):
        job = _collect_one(_fake_df(currency=float("nan"), interval=float("nan")))
        assert job.salary_currency is None
        assert job.salary_interval is None


class TestMaxAgeFilter:
    def test_hours_old_passed_to_jobspy(self):
        collector = JobSpyCollector(max_age_days=30)
        with patch(
            "tycho.collector.jobspy_collector.scrape_jobs", return_value=_fake_df()
        ) as mock_scrape:
            collector.collect(search_terms=["ml"], locations=["Madrid"])
        assert mock_scrape.call_args.kwargs["hours_old"] == 30 * 24

    def test_hours_old_omitted_when_unset(self):
        collector = JobSpyCollector()
        with patch(
            "tycho.collector.jobspy_collector.scrape_jobs", return_value=_fake_df()
        ) as mock_scrape:
            collector.collect(search_terms=["ml"], locations=["Madrid"])
        assert "hours_old" not in mock_scrape.call_args.kwargs

    def test_old_jobs_dropped(self):
        old_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        collector = JobSpyCollector(max_age_days=30)
        with patch(
            "tycho.collector.jobspy_collector.scrape_jobs",
            return_value=_fake_df(date_posted=old_date),
        ):
            jobs = collector.collect(search_terms=["ml"], locations=["Madrid"])
        assert jobs == []

    def test_recent_jobs_kept(self):
        recent_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        collector = JobSpyCollector(max_age_days=30)
        with patch(
            "tycho.collector.jobspy_collector.scrape_jobs",
            return_value=_fake_df(date_posted=recent_date),
        ):
            jobs = collector.collect(search_terms=["ml"], locations=["Madrid"])
        assert len(jobs) == 1

    def test_unknown_date_kept(self):
        collector = JobSpyCollector(max_age_days=30)
        with patch(
            "tycho.collector.jobspy_collector.scrape_jobs",
            return_value=_fake_df(date_posted=None),
        ):
            jobs = collector.collect(search_terms=["ml"], locations=["Madrid"])
        assert len(jobs) == 1
        assert jobs[0].date_posted is None

    def test_no_filter_when_max_age_unset(self):
        old_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        collector = JobSpyCollector()
        with patch(
            "tycho.collector.jobspy_collector.scrape_jobs",
            return_value=_fake_df(date_posted=old_date),
        ):
            jobs = collector.collect(search_terms=["ml"], locations=["Madrid"])
        assert len(jobs) == 1


def _li_df(*ids):
    return pd.DataFrame(
        [
            {
                "site": "linkedin", "id": i, "title": f"T {i}", "company": "Acme",
                "location": "Madrid", "description": None,
                "job_url": f"https://www.linkedin.com/jobs/view/{i[3:]}",
                "date_posted": "2026-11-24",
            }
            for i in ids
        ]
    )


class TestSkipKnownLinkedIn:
    def _run(self, df, known, searches=1):
        collector = JobSpyCollector(known_ids=known)
        with patch("tycho.collector.jobspy_collector.scrape_jobs", return_value=df) as scrape, \
             patch.object(JobSpyCollector, "_fetch_linkedin_description", return_value="DESC") as fetch:
            jobs = collector.collect(search_terms=["ml"] * searches, locations=["Madrid"])
        return jobs, scrape, fetch

    def test_known_dropped_and_only_new_fetched(self):
        jobs, scrape, fetch = self._run(_li_df("li-1", "li-2"), {"linkedin": {"li-1"}})
        assert [j.source_id for j in jobs] == ["li-2"]
        assert jobs[0].description == "DESC"
        fetch.assert_called_once_with("li-2")
        assert scrape.call_args.kwargs["linkedin_fetch_description"] is False

    def test_same_id_in_two_searches_fetched_once(self):
        jobs, _, fetch = self._run(_li_df("li-9"), {}, searches=2)
        assert len(jobs) == 1
        assert fetch.call_count == 1

    def test_indeed_rows_kept_even_if_known(self):
        df = _fake_df()  # indeed, has its own description
        jobs, _, fetch = self._run(df, {"indeed": {"in-123"}})
        assert len(jobs) == 1 and jobs[0].description == "Do ML things"
        fetch.assert_not_called()

    def test_without_known_ids_behaviour_unchanged(self):
        collector = JobSpyCollector()
        with patch("tycho.collector.jobspy_collector.scrape_jobs", return_value=_li_df("li-1")) as scrape:
            collector.collect(search_terms=["ml"], locations=["Madrid"])
        assert scrape.call_args.kwargs["linkedin_fetch_description"] is True

    def test_fetch_failure_keeps_job_with_empty_description(self):
        collector = JobSpyCollector(known_ids={})
        with patch("tycho.collector.jobspy_collector.scrape_jobs", return_value=_li_df("li-5")), \
             patch.object(JobSpyCollector, "_fetch_linkedin_description", side_effect=RuntimeError("x")):
            jobs = collector.collect(search_terms=["ml"], locations=["Madrid"])
        assert len(jobs) == 1 and jobs[0].description == ""

    def test_fetch_uses_numeric_id(self):
        collector = JobSpyCollector(known_ids={})
        with patch("tycho.collector.jobspy_collector.LinkedIn") as li:
            li.return_value._get_job_details.return_value = {"description": "hi"}
            assert collector._fetch_linkedin_description("li-42") == "hi"
            li.return_value._get_job_details.assert_called_once_with("42")

    def test_row_without_id_passes_through_and_does_not_block_others(self):
        df = _li_df("li-1", "li-2")
        df.loc[0, "id"] = ""
        jobs, _, fetch = self._run(df, {})
        assert [j.source_id for j in jobs] == ["", "li-2"]
        fetch.assert_called_once_with("li-2")

    def test_stale_rows_not_fetched_nor_counted(self, capsys):
        old = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        df = _li_df("li-1", "li-2")
        df.loc[0, "date_posted"] = old
        collector = JobSpyCollector(known_ids={}, max_age_days=7)
        with patch("tycho.collector.jobspy_collector.scrape_jobs", return_value=df), \
             patch.object(JobSpyCollector, "_fetch_linkedin_description", return_value="D") as fetch:
            jobs = collector.collect(search_terms=["ml"], locations=["Madrid"])
        assert [j.source_id for j in jobs] == ["li-2"]
        fetch.assert_called_once_with("li-2")
        assert collector.term_stats["ml"] == [1, 0]

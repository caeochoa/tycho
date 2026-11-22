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

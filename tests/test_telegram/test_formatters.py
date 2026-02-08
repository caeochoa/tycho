"""Tests for Telegram message formatters."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from tycho.models import Job, JobStatus
from tycho.telegram.formatters import (
    format_job_detail,
    format_job_line,
    format_schedule_status,
)


class TestFormatJobLine:
    def test_high_score_green(self, ml_job):
        ml_job.score = 0.85
        line = format_job_line(ml_job, 1)
        assert "1." in line
        assert "0.85" in line
        assert "ML" in line or "Machine Learning" in line
        assert "\U0001f7e2" in line  # green circle

    def test_medium_score_yellow(self, backend_job):
        backend_job.score = 0.55
        line = format_job_line(backend_job, 2)
        assert "0.55" in line
        assert "\U0001f7e1" in line  # yellow circle

    def test_low_score_red(self, empty_job):
        empty_job.score = 0.20
        line = format_job_line(empty_job, 3)
        assert "0.20" in line
        assert "\U0001f534" in line  # red circle

    def test_no_score(self, empty_job):
        empty_job.score = None
        line = format_job_line(empty_job, 1)
        assert "-.--" in line
        assert "\u26aa" in line  # white circle

    def test_html_escaping(self):
        job = Job(
            id="test-esc", source="test", title="<b>Hacker</b>",
            company="Corp & Co", location="A > B",
        )
        line = format_job_line(job, 1)
        assert "&lt;b&gt;" in line
        assert "&amp;" in line
        assert "&gt;" in line

    def test_empty_location(self):
        job = Job(id="test-loc", source="test", title="Test", company="Corp", location="")
        line = format_job_line(job, 1)
        # No trailing parentheses
        assert "()" not in line


class TestFormatJobDetail:
    def test_includes_title_and_company(self, ml_job):
        ml_job.score = 0.85
        ml_job.score_details = {
            "keyword_match": 0.9, "title_match": 0.8,
            "skills_overlap": 0.7, "location_match": 1.0,
        }
        text = format_job_detail(ml_job)
        assert "<b>" in text
        assert "DeepTech AI" in text
        assert "Madrid" in text

    def test_includes_score_breakdown(self, ml_job):
        ml_job.score = 0.85
        ml_job.score_details = {
            "keyword_match": 0.9, "title_match": 0.8,
            "skills_overlap": 0.7, "location_match": 1.0,
        }
        text = format_job_detail(ml_job)
        assert "0.85" in text
        assert "Keyword Match" in text
        assert "0.90" in text

    def test_includes_salary(self):
        job = Job(
            id="test-sal", source="test", title="Dev", company="Co",
            salary_min=50000, salary_max=80000,
        )
        text = format_job_detail(job)
        assert "50,000" in text
        assert "80,000" in text

    def test_includes_status(self, backend_job):
        text = format_job_detail(backend_job)
        assert backend_job.status.value in text

    def test_includes_keywords(self):
        job = Job(
            id="test-kw", source="test", title="Dev", company="Co",
            score=0.5,
            score_details={"job_keywords": ["python", "docker"]},
        )
        text = format_job_detail(job)
        assert "python" in text
        assert "docker" in text

    def test_description_truncated(self):
        job = Job(
            id="test-desc", source="test", title="Dev", company="Co",
            description="x" * 500,
        )
        text = format_job_detail(job)
        assert "..." in text
        assert len(text) < 600

    def test_no_score(self, empty_job):
        text = format_job_detail(empty_job)
        # Should not crash
        assert "Score" not in text


class TestFormatScheduleStatus:
    def test_enabled_scheduler(self):
        config = MagicMock()
        config.scheduler.enabled = True
        config.scheduler.cron = "0 8 * * *"
        next_run = datetime(2026, 2, 9, 8, 0)
        text = format_schedule_status(config, [], next_run)
        assert "Active" in text
        assert "0 8 * * *" in text
        assert "2026-02-09" in text

    def test_disabled_scheduler(self):
        config = MagicMock()
        config.scheduler.enabled = False
        text = format_schedule_status(config, [], None)
        assert "Disabled" in text

    def test_with_runs(self):
        config = MagicMock()
        config.scheduler.enabled = True
        config.scheduler.cron = "0 8 * * *"

        run = MagicMock()
        run.status = "success"
        run.timestamp = datetime(2026, 2, 8, 8, 0)
        run.raw_count = 50
        run.deduped_count = 45
        run.new_count = 3

        text = format_schedule_status(config, [run], None)
        assert "50 raw" in text
        assert "45 dedup" in text
        assert "3 new" in text
        assert "\u2705" in text

    def test_failed_run(self):
        config = MagicMock()
        config.scheduler.enabled = True
        config.scheduler.cron = "0 8 * * *"

        run = MagicMock()
        run.status = "error"
        run.timestamp = datetime(2026, 2, 8, 8, 0)
        run.raw_count = 0
        run.deduped_count = 0
        run.new_count = 0

        text = format_schedule_status(config, [run], None)
        assert "\u274c" in text

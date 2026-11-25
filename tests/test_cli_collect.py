"""Tests for the collect CLI command's company wiring."""

from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from tycho.cli import app
from tycho.models import Job

runner = CliRunner()


def _write_config(tmp_path, **extra):
    data = {
        "db_path": str(tmp_path / "test.db"),
        "companies": [{"name": "Acme", "url": "https://boards.greenhouse.io/acme"}],
        "llm": {"enabled": False},
        **extra,
    }
    (tmp_path / "config.yaml").write_text(yaml.dump(data))


def _company_job():
    return Job(
        id="cli-1", source="greenhouse", source_id="gh-1",
        title="ML Engineer", company="Acme", description="ML role",
    )


class TestCollectCompanies:
    def test_companies_only_skips_jobspy(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        with patch("tycho.collector.jobspy_collector.JobSpyCollector") as mock_jobspy, patch(
            "tycho.collector.company_collector.collect_company_jobs",
            return_value=[_company_job()],
        ) as mock_companies:
            result = runner.invoke(app, ["collect", "--companies-only"])
        assert result.exit_code == 0, result.output
        mock_jobspy.assert_not_called()
        mock_companies.assert_called_once()
        assert "1 new jobs" in result.output

    def test_no_companies_skips_company_boards(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        with patch("tycho.collector.jobspy_collector.JobSpyCollector") as mock_jobspy, patch(
            "tycho.collector.company_collector.collect_company_jobs"
        ) as mock_companies:
            mock_jobspy.return_value.collect.return_value = []
            result = runner.invoke(app, ["collect", "--no-companies"])
        assert result.exit_code == 0, result.output
        mock_companies.assert_not_called()

    def test_max_age_days_passed_to_collector(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, search={"max_age_days": 7})
        with patch("tycho.collector.jobspy_collector.JobSpyCollector") as mock_jobspy, patch(
            "tycho.collector.company_collector.collect_company_jobs", return_value=[]
        ):
            mock_jobspy.return_value.collect.return_value = []
            result = runner.invoke(app, ["collect"])
        assert result.exit_code == 0, result.output
        assert mock_jobspy.call_args.kwargs["max_age_days"] == 7

    def test_default_runs_both(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        with patch("tycho.collector.jobspy_collector.JobSpyCollector") as mock_jobspy, patch(
            "tycho.collector.company_collector.collect_company_jobs",
            return_value=[_company_job()],
        ) as mock_companies:
            mock_jobspy.return_value.collect.return_value = []
            result = runner.invoke(app, ["collect"])
        assert result.exit_code == 0, result.output
        mock_jobspy.assert_called_once()
        mock_companies.assert_called_once()


class TestCollectScheduleRun:
    def _runs(self, tmp_path):
        from tycho.db import get_schedule_runs, get_session, init_db

        session = get_session(init_db(str(tmp_path / "test.db")))
        try:
            return get_schedule_runs(session)
        finally:
            session.close()

    def test_success_writes_row(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        with patch(
            "tycho.collector.company_collector.collect_company_jobs",
            return_value=[_company_job()],
        ):
            result = runner.invoke(app, ["collect", "--companies-only"])
        assert result.exit_code == 0, result.output
        runs = self._runs(tmp_path)
        assert len(runs) == 1
        assert (runs[0].status, runs[0].raw_count, runs[0].deduped_count, runs[0].new_count) == ("success", 1, 1, 1)

    def test_failure_writes_error_row_and_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        with patch(
            "tycho.collector.company_collector.collect_company_jobs",
            side_effect=RuntimeError("boom"),
        ):
            result = runner.invoke(app, ["collect", "--companies-only"])
        assert result.exit_code != 0
        runs = self._runs(tmp_path)
        assert len(runs) == 1
        assert runs[0].status == "error" and "boom" in runs[0].error_message

    def test_max_age_days_flag_overrides_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, search={"max_age_days": 3})
        with patch("tycho.collector.jobspy_collector.JobSpyCollector") as mock_jobspy, patch(
            "tycho.collector.company_collector.collect_company_jobs", return_value=[]
        ):
            mock_jobspy.return_value.collect.return_value = []
            runner.invoke(app, ["collect", "--max-age-days", "30"])
        assert mock_jobspy.call_args.kwargs["max_age_days"] == 30

    def test_all_searches_failed_records_error_and_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        with patch("tycho.collector.jobspy_collector.JobSpyCollector") as mock_jobspy, patch(
            "tycho.collector.company_collector.collect_company_jobs", return_value=[]
        ):
            c = mock_jobspy.return_value
            c.collect.return_value = []
            c.all_searches_failed = True
            c.searches_attempted = 4
            result = runner.invoke(app, ["collect"])
        assert result.exit_code == 1
        runs = self._runs(tmp_path)
        assert runs[0].status == "error" and "all 4" in runs[0].error_message

    def test_record_failure_does_not_mask_original_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path)
        with patch(
            "tycho.collector.company_collector.collect_company_jobs",
            side_effect=RuntimeError("original"),
        ), patch("tycho.db.record_run", side_effect=OSError("db locked")):
            result = runner.invoke(app, ["collect", "--companies-only"])
        assert isinstance(result.exception, RuntimeError) and "original" in str(result.exception)

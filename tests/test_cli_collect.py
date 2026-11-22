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

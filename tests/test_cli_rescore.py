"""Tests for the rescore CLI command."""

import os

import yaml
from typer.testing import CliRunner

from tycho.cli import app
from tycho.db import get_engine, get_session, init_db, upsert_job
from tycho.models import Job

runner = CliRunner()

REAL_PROFILE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "profile")
)


def _write_config(tmp_path):
    data = {
        "db_path": str(tmp_path / "test.db"),
        "profile_dir": REAL_PROFILE_DIR,
        "llm": {"enabled": False},
    }
    (tmp_path / "config.yaml").write_text(yaml.dump(data))
    return str(tmp_path / "test.db")


def _seed_jobs(db_path, count):
    engine = init_db(db_path)
    session = get_session(engine)
    for i in range(count):
        job = Job(
            id=f"job-{i}", source="test", source_id=f"t{i}",
            title="AI Engineer", company="Corp", description="Python role",
        )
        upsert_job(session, job)
    session.commit()
    session.close()


class TestRescore:
    def test_rescores_every_job_not_just_first_10000(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db_path = _write_config(tmp_path)
        _seed_jobs(db_path, 3)

        captured = {}
        import tycho.db as db_module
        real_get_jobs = db_module.get_jobs

        def spy_get_jobs(*args, **kwargs):
            captured["limit"] = kwargs.get("limit")
            return real_get_jobs(*args, **kwargs)

        monkeypatch.setattr(db_module, "get_jobs", spy_get_jobs)

        result = runner.invoke(app, ["rescore"])

        assert result.exit_code == 0, result.output
        # A hardcoded numeric cap would silently drop jobs once the DB exceeds it.
        assert captured["limit"] is None

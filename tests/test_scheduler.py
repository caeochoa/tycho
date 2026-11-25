"""Tests for the scheduler module."""

import pytest

from tycho.scheduler.scheduler import parse_cron


class TestParseCron:
    def test_daily_8am(self):
        result = parse_cron("0 8 * * *")
        assert result == {
            "minute": "0",
            "hour": "8",
            "day": "*",
            "month": "*",
            "day_of_week": "*",
        }

    def test_every_2_minutes(self):
        result = parse_cron("*/2 * * * *")
        assert result["minute"] == "*/2"

    def test_weekly_monday(self):
        result = parse_cron("30 9 * * 1")
        assert result == {
            "minute": "30",
            "hour": "9",
            "day": "*",
            "month": "*",
            "day_of_week": "1",
        }

    def test_invalid_cron_too_few_parts(self):
        with pytest.raises(ValueError, match="Invalid cron"):
            parse_cron("0 8 *")

    def test_invalid_cron_too_many_parts(self):
        with pytest.raises(ValueError, match="Invalid cron"):
            parse_cron("0 8 * * * *")

    def test_empty_string(self):
        with pytest.raises(ValueError, match="Invalid cron"):
            parse_cron("")


class TestScheduleRunDB:
    def test_add_and_retrieve_schedule_run(self, tmp_path):
        from tycho.db import add_schedule_run, get_schedule_runs, get_session, init_db

        db_path = str(tmp_path / "test.db")
        engine = init_db(db_path)
        session = get_session(engine)

        add_schedule_run(session, raw_count=100, deduped_count=80, new_count=30)
        session.commit()

        runs = get_schedule_runs(session, limit=10)
        assert len(runs) == 1
        assert runs[0].raw_count == 100
        assert runs[0].deduped_count == 80
        assert runs[0].new_count == 30
        assert runs[0].status == "success"
        session.close()

    def test_error_run(self, tmp_path):
        from tycho.db import add_schedule_run, get_schedule_runs, get_session, init_db

        db_path = str(tmp_path / "test.db")
        engine = init_db(db_path)
        session = get_session(engine)

        add_schedule_run(session, status="error", error_message="Connection timeout")
        session.commit()

        runs = get_schedule_runs(session)
        assert len(runs) == 1
        assert runs[0].status == "error"
        assert runs[0].error_message == "Connection timeout"
        session.close()

    def test_multiple_runs_ordered(self, tmp_path):
        import time

        from tycho.db import add_schedule_run, get_schedule_runs, get_session, init_db

        db_path = str(tmp_path / "test.db")
        engine = init_db(db_path)
        session = get_session(engine)

        add_schedule_run(session, new_count=10)
        session.commit()
        time.sleep(0.01)
        add_schedule_run(session, new_count=20)
        session.commit()

        runs = get_schedule_runs(session, limit=10)
        assert len(runs) == 2
        # Most recent first
        assert runs[0].new_count == 20
        assert runs[1].new_count == 10
        session.close()


class TestGetJobByPrefix:
    def test_exact_match(self, tmp_path):
        from tycho.db import get_job_by_prefix, get_session, init_db, upsert_job
        from tycho.models import Job

        db_path = str(tmp_path / "test.db")
        engine = init_db(db_path)
        session = get_session(engine)

        job = Job(id="abc-123", source="test", source_id="t1", title="Dev", company="Corp")
        upsert_job(session, job)
        session.commit()

        found, err = get_job_by_prefix(session, "abc-123")
        assert found is not None
        assert found.id == "abc-123"
        assert err is None
        session.close()

    def test_prefix_match(self, tmp_path):
        from tycho.db import get_job_by_prefix, get_session, init_db, upsert_job
        from tycho.models import Job

        db_path = str(tmp_path / "test.db")
        engine = init_db(db_path)
        session = get_session(engine)

        job = Job(id="abc-123-full", source="test", source_id="t1", title="Dev", company="Corp")
        upsert_job(session, job)
        session.commit()

        found, err = get_job_by_prefix(session, "abc-123")
        assert found is not None
        assert found.id == "abc-123-full"
        assert err is None
        session.close()

    def test_ambiguous_prefix(self, tmp_path):
        from tycho.db import get_job_by_prefix, get_session, init_db, upsert_job
        from tycho.models import Job

        db_path = str(tmp_path / "test.db")
        engine = init_db(db_path)
        session = get_session(engine)

        upsert_job(session, Job(id="abc-111", source="test", source_id="t1", title="Dev1", company="Corp"))
        upsert_job(session, Job(id="abc-222", source="test", source_id="t2", title="Dev2", company="Corp"))
        session.commit()

        found, err = get_job_by_prefix(session, "abc")
        assert found is None
        assert "Ambiguous" in err
        session.close()

    def test_not_found(self, tmp_path):
        from tycho.db import get_job_by_prefix, get_session, init_db

        db_path = str(tmp_path / "test.db")
        engine = init_db(db_path)
        session = get_session(engine)

        found, err = get_job_by_prefix(session, "xyz")
        assert found is None
        assert "not found" in err
        session.close()


class TestGetJobsPaginated:
    def test_basic_pagination(self, tmp_path):
        from tycho.db import get_jobs_paginated, get_session, init_db, upsert_job
        from tycho.models import Job

        db_path = str(tmp_path / "test.db")
        engine = init_db(db_path)
        session = get_session(engine)

        for i in range(10):
            upsert_job(session, Job(
                id=f"job-{i}", source="test", source_id=f"t{i}",
                title=f"Job {i}", company="Corp", score=float(i) / 10,
            ))
        session.commit()

        jobs, total = get_jobs_paginated(session, limit=3, offset=0)
        assert total == 10
        assert len(jobs) == 3
        session.close()

    def test_search_filter(self, tmp_path):
        from tycho.db import get_jobs_paginated, get_session, init_db, upsert_job
        from tycho.models import Job

        db_path = str(tmp_path / "test.db")
        engine = init_db(db_path)
        session = get_session(engine)

        upsert_job(session, Job(id="j1", source="test", source_id="t1", title="ML Engineer", company="AI Corp"))
        upsert_job(session, Job(id="j2", source="test", source_id="t2", title="Frontend Dev", company="Web Inc"))
        session.commit()

        jobs, total = get_jobs_paginated(session, search="ML")
        assert total == 1
        assert jobs[0].title == "ML Engineer"
        session.close()


class TestCollectionTaskCompanies:
    def test_company_jobs_collected_and_stored(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from tycho.config import CompanyConfig, TychoConfig
        from tycho.db import get_jobs, get_session, init_db
        from tycho.models import Job
        from tycho.scheduler.scheduler import collection_task

        config = TychoConfig(
            db_path=str(tmp_path / "test.db"),
            companies=[
                CompanyConfig(name="Acme", url="https://boards.greenhouse.io/acme")
            ],
        )
        engine = init_db(config.db_path)
        company_job = Job(
            id="cj-1", source="greenhouse", source_id="gh-1",
            title="ML Engineer", company="Acme", description="ML role",
        )

        with patch("tycho.collector.jobspy_collector.JobSpyCollector") as mock_jobspy, patch(
            "tycho.collector.company_collector.collect_company_jobs",
            return_value=[company_job],
        ) as mock_companies:
            mock_jobspy.return_value.collect.return_value = []
            collection_task(config, engine)

        mock_companies.assert_called_once_with(config)
        session = get_session(engine)
        stored = get_jobs(session, limit=10)
        session.close()
        assert len(stored) == 1
        assert stored[0].company == "Acme"
        assert stored[0].source == "greenhouse"

    def test_max_age_days_passed_to_collector(self, tmp_path):
        from unittest.mock import patch

        from tycho.config import TychoConfig
        from tycho.db import init_db
        from tycho.scheduler.scheduler import collection_task

        config = TychoConfig(db_path=str(tmp_path / "test.db"))
        config.search.max_age_days = 7
        engine = init_db(config.db_path)

        with patch("tycho.collector.jobspy_collector.JobSpyCollector") as mock_jobspy:
            mock_jobspy.return_value.collect.return_value = []
            collection_task(config, engine)

        assert mock_jobspy.call_args.kwargs["max_age_days"] == 7


class TestKnownIdsAndCollectionTask:
    def test_get_known_source_ids(self, tmp_path):
        from tycho.db import get_known_source_ids, get_session, init_db, upsert_job
        from tycho.models import Job

        session = get_session(init_db(str(tmp_path / "k.db")))
        upsert_job(session, Job(id="a", source="linkedin", source_id="li-1", title="t", company="c", description="d"))
        upsert_job(session, Job(id="b", source="indeed", source_id="in-2", title="t", company="c", description="d"))
        # empty / whitespace descriptions are not "known": they get retried
        upsert_job(session, Job(id="c", source="linkedin", source_id="li-3", title="t", company="c", description=""))
        upsert_job(session, Job(id="d", source="linkedin", source_id="li-4", title="t", company="c", description="  "))
        session.commit()
        assert get_known_source_ids(session) == {"linkedin": {"li-1"}, "indeed": {"in-2"}}

    def test_collection_task_records_run(self, tmp_path):
        from unittest.mock import patch

        from tycho.config import TychoConfig
        from tycho.db import get_schedule_runs, get_session, init_db
        from tycho.scheduler.scheduler import collection_task

        engine = init_db(str(tmp_path / "c.db"))
        with patch("tycho.collector.jobspy_collector.JobSpyCollector") as jc:
            jc.return_value.collect.return_value = []
            collection_task(TychoConfig(db_path=str(tmp_path / "c.db")), engine)
        runs = get_schedule_runs(get_session(engine))
        assert len(runs) == 1 and runs[0].status == "success"

    def test_collection_task_records_error_when_all_searches_failed(self, tmp_path):
        from unittest.mock import patch

        from tycho.config import TychoConfig
        from tycho.db import get_schedule_runs, get_session, init_db
        from tycho.scheduler.scheduler import collection_task

        engine = init_db(str(tmp_path / "f.db"))
        with patch("tycho.collector.jobspy_collector.JobSpyCollector") as jc:
            jc.return_value.collect.return_value = []
            jc.return_value.all_searches_failed = True
            jc.return_value.searches_attempted = 3
            collection_task(TychoConfig(db_path=str(tmp_path / "f.db")), engine)
        runs = get_schedule_runs(get_session(engine))
        assert runs[0].status == "error" and "all 3" in runs[0].error_message

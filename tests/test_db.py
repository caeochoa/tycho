"""Tests for database operations."""

import json
from datetime import datetime

import pytest

from tycho.db import (
    get_job_by_id,
    get_jobs,
    get_session,
    init_db,
    job_to_row,
    row_to_job,
    update_job_paths,
    update_job_score,
    update_job_status,
    upsert_job,
)
from tycho.models import Job, JobStatus


@pytest.fixture
def db_session(tmp_path):
    db_path = str(tmp_path / "test.db")
    engine = init_db(db_path)
    session = get_session(engine)
    yield session
    session.close()


@pytest.fixture
def sample_db_job():
    return Job(
        id="test-123",
        source="indeed",
        source_id="indeed_456",
        title="ML Engineer",
        company="AI Corp",
        location="Madrid",
        description="Great ML role",
        url="https://example.com",
        salary_min=50000.0,
        salary_max=80000.0,
        date_posted=datetime(2025, 1, 15),
        tags=["python", "ml"],
        score=0.85,
        score_details={"keyword_match": 0.9, "title_match": 0.8},
        status=JobStatus.NEW,
    )


class TestJobConversion:
    def test_job_to_row_and_back(self, sample_db_job):
        row = job_to_row(sample_db_job)
        assert row.id == "test-123"
        assert row.tags == '["python", "ml"]'
        assert row.score == 0.85
        assert json.loads(row.score_details)["keyword_match"] == 0.9
        assert row.status == "new"

        job = row_to_job(row)
        assert job.id == "test-123"
        assert job.tags == ["python", "ml"]
        assert job.score == 0.85
        assert job.score_details["keyword_match"] == 0.9
        assert job.status == JobStatus.NEW

    def test_none_score_details(self):
        job = Job(id="1", source="test", source_id="t1", title="Dev", company="Corp")
        row = job_to_row(job)
        assert row.score_details is None
        assert row.score is None

        job_back = row_to_job(row)
        assert job_back.score is None
        assert job_back.score_details is None

    def test_empty_tags(self):
        job = Job(id="1", source="test", source_id="t1", title="Dev", company="Corp")
        row = job_to_row(job)
        assert row.tags == "[]"

        job_back = row_to_job(row)
        assert job_back.tags == []


class TestUpsertJob:
    def test_insert_new_job(self, db_session, sample_db_job):
        is_new = upsert_job(db_session, sample_db_job)
        db_session.commit()
        assert is_new is True

        retrieved = get_job_by_id(db_session, "test-123")
        assert retrieved is not None
        assert retrieved.title == "ML Engineer"

    def test_update_existing_job(self, db_session, sample_db_job):
        upsert_job(db_session, sample_db_job)
        db_session.commit()

        # Same source + source_id, different title
        updated = Job(
            id="different-id",
            source="indeed",
            source_id="indeed_456",
            title="Senior ML Engineer",
            company="AI Corp",
            description="Updated description",
        )
        is_new = upsert_job(db_session, updated)
        db_session.commit()
        assert is_new is False

        # Should keep original ID, update title and description
        retrieved = get_job_by_id(db_session, "test-123")
        assert retrieved.title == "Senior ML Engineer"
        assert retrieved.description == "Updated description"

    def test_different_source_id_creates_new(self, db_session, sample_db_job):
        upsert_job(db_session, sample_db_job)
        db_session.commit()

        other = Job(
            id="other-id",
            source="indeed",
            source_id="indeed_789",
            title="Different Job",
            company="Other Corp",
        )
        is_new = upsert_job(db_session, other)
        db_session.commit()
        assert is_new is True


class TestGetJobs:
    def test_empty_db(self, db_session):
        jobs = get_jobs(db_session)
        assert jobs == []

    def test_get_all(self, db_session):
        for i in range(5):
            job = Job(id=f"job-{i}", source="test", source_id=f"t{i}", title=f"Job {i}", company="Corp")
            upsert_job(db_session, job)
        db_session.commit()

        jobs = get_jobs(db_session)
        assert len(jobs) == 5

    def test_filter_by_status(self, db_session):
        job1 = Job(id="j1", source="test", source_id="t1", title="Job 1", company="Corp", status=JobStatus.NEW)
        job2 = Job(id="j2", source="test", source_id="t2", title="Job 2", company="Corp", status=JobStatus.INTERESTED)
        upsert_job(db_session, job1)
        upsert_job(db_session, job2)
        db_session.commit()

        new_jobs = get_jobs(db_session, status="new")
        assert len(new_jobs) == 1
        assert new_jobs[0].id == "j1"

    def test_filter_by_min_score(self, db_session):
        job1 = Job(id="j1", source="test", source_id="t1", title="Job", company="Corp", score=0.3)
        job2 = Job(id="j2", source="test", source_id="t2", title="Job", company="Corp", score=0.8)
        upsert_job(db_session, job1)
        upsert_job(db_session, job2)
        db_session.commit()

        jobs = get_jobs(db_session, min_score=0.5)
        assert len(jobs) == 1
        assert jobs[0].score == 0.8

    def test_limit(self, db_session):
        for i in range(10):
            job = Job(id=f"job-{i}", source="test", source_id=f"t{i}", title=f"Job {i}", company="Corp")
            upsert_job(db_session, job)
        db_session.commit()

        jobs = get_jobs(db_session, limit=3)
        assert len(jobs) == 3

    def test_ordered_by_score_desc(self, db_session):
        for i, score in enumerate([0.3, 0.9, 0.5]):
            job = Job(id=f"job-{i}", source="test", source_id=f"t{i}", title="Job", company="Corp", score=score)
            upsert_job(db_session, job)
        db_session.commit()

        jobs = get_jobs(db_session)
        scores = [j.score for j in jobs]
        assert scores == sorted(scores, reverse=True)


class TestGetJobById:
    def test_found(self, db_session, sample_db_job):
        upsert_job(db_session, sample_db_job)
        db_session.commit()

        job = get_job_by_id(db_session, "test-123")
        assert job is not None
        assert job.title == "ML Engineer"

    def test_not_found(self, db_session):
        job = get_job_by_id(db_session, "nonexistent")
        assert job is None


class TestUpdateFunctions:
    def test_update_status(self, db_session, sample_db_job):
        upsert_job(db_session, sample_db_job)
        db_session.commit()

        found = update_job_status(db_session, "test-123", "interested")
        db_session.commit()
        assert found is True

        job = get_job_by_id(db_session, "test-123")
        assert job.status == JobStatus.INTERESTED

    def test_update_status_not_found(self, db_session):
        found = update_job_status(db_session, "nonexistent", "interested")
        assert found is False

    def test_update_score(self, db_session, sample_db_job):
        upsert_job(db_session, sample_db_job)
        db_session.commit()

        update_job_score(db_session, "test-123", 0.95, {"keyword_match": 1.0})
        db_session.commit()

        job = get_job_by_id(db_session, "test-123")
        assert job.score == 0.95
        assert job.score_details["keyword_match"] == 1.0

    def test_update_paths(self, db_session, sample_db_job):
        upsert_job(db_session, sample_db_job)
        db_session.commit()

        update_job_paths(db_session, "test-123", cv_path="/output/cv.pdf")
        db_session.commit()

        job = get_job_by_id(db_session, "test-123")
        assert job.cv_path == "/output/cv.pdf"

    def test_update_paths_both(self, db_session, sample_db_job):
        upsert_job(db_session, sample_db_job)
        db_session.commit()

        update_job_paths(db_session, "test-123", cv_path="/cv.pdf", cover_letter_path="/cl.pdf")
        db_session.commit()

        job = get_job_by_id(db_session, "test-123")
        assert job.cv_path == "/cv.pdf"
        assert job.cover_letter_path == "/cl.pdf"

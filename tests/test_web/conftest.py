"""Shared fixtures for web tests."""

import pytest
from fastapi.testclient import TestClient

from tycho.config import TychoConfig
from tycho.db import Base, get_session, init_db, upsert_job
from tycho.models import Job, JobStatus
from tycho.web.app import create_app


@pytest.fixture
def web_db(tmp_path):
    """Create a test database and return (engine, db_path)."""
    db_path = str(tmp_path / "test_web.db")
    engine = init_db(db_path)
    return engine, db_path


@pytest.fixture
def web_app(tmp_path, web_db):
    """Create a test FastAPI app with test DB."""
    engine, db_path = web_db

    app = create_app()
    # Override app state with test DB
    app.state.config = TychoConfig(db_path=db_path, output_dir=str(tmp_path / "output"))
    app.state.engine = engine

    return app


@pytest.fixture
def client(web_app):
    """Create a test client."""
    return TestClient(web_app, raise_server_exceptions=False)


@pytest.fixture
def seeded_client(web_app, web_db):
    """Create a test client with sample jobs in the database."""
    engine, _ = web_db
    session = get_session(engine)

    jobs = [
        Job(
            id="job-ml-001",
            source="indeed",
            source_id="indeed_ml_001",
            title="ML Engineer",
            company="DeepTech AI",
            location="Madrid, Spain",
            description="Looking for ML engineer with Python and PyTorch.",
            score=0.85,
            score_details={"keyword_match": 0.9, "title_match": 0.8, "skills_overlap": 0.7, "location_match": 1.0},
            status=JobStatus.NEW,
        ),
        Job(
            id="job-be-002",
            source="linkedin",
            source_id="linkedin_be_002",
            title="Backend Developer",
            company="WebCorp",
            location="London, UK",
            description="Backend role with Python and FastAPI.",
            score=0.60,
            status=JobStatus.INTERESTED,
        ),
        Job(
            id="job-ds-003",
            source="indeed",
            source_id="indeed_ds_003",
            title="Data Scientist",
            company="DataInc",
            location="Remote",
            description="Data science role with pandas and SQL.",
            score=0.40,
            status=JobStatus.NEW,
        ),
    ]
    for job in jobs:
        upsert_job(session, job)
    session.commit()
    session.close()

    return TestClient(web_app, raise_server_exceptions=False)

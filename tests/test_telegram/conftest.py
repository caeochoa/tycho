"""Shared fixtures for Telegram bot tests."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from tycho.config import TychoConfig
from tycho.db import get_session, init_db, upsert_job
from tycho.models import Job, JobStatus


@pytest.fixture
def tg_db(tmp_path):
    """Create a test database and return engine."""
    db_path = str(tmp_path / "test_tg.db")
    engine = init_db(db_path)
    return engine, db_path


@pytest.fixture
def tg_config(tmp_path, tg_db):
    """TychoConfig with test DB and telegram enabled."""
    _, db_path = tg_db
    return TychoConfig(
        db_path=db_path,
        output_dir=str(tmp_path / "output"),
        telegram={"enabled": True, "token": "test-token", "allowed_users": [], "page_size": 3},
    )


@pytest.fixture
def seeded_db(tg_db):
    """Seed the test DB with sample jobs."""
    engine, _ = tg_db
    session = get_session(engine)
    jobs = [
        Job(
            id="aaaaaaaa-1111-2222-3333-444444444444",
            source="indeed",
            source_id="indeed_ml_001",
            title="ML Engineer",
            company="DeepTech AI",
            location="Madrid, Spain",
            description="Looking for ML engineer with Python and PyTorch.",
            url="https://example.com/job/ml",
            score=0.85,
            score_details={
                "keyword_match": 0.9, "title_match": 0.8,
                "skills_overlap": 0.7, "location_match": 1.0,
                "job_keywords": ["python", "pytorch", "ml"],
            },
            status=JobStatus.NEW,
            salary_min=45000,
            salary_max=65000,
        ),
        Job(
            id="bbbbbbbb-1111-2222-3333-444444444444",
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
            id="cccccccc-1111-2222-3333-444444444444",
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
    return engine


@pytest.fixture
def bot_data(tg_config, seeded_db):
    """bot_data dict as stored on the Telegram Application."""
    return {
        "config": tg_config,
        "engine": seeded_db,
        "scheduler": None,
    }


@pytest.fixture
def make_context(bot_data):
    """Factory for mock ContextTypes.DEFAULT_TYPE."""
    def _make(user_data=None):
        ctx = MagicMock()
        ctx.bot_data = bot_data
        ctx.user_data = user_data if user_data is not None else {}
        ctx.bot = AsyncMock()
        return ctx
    return _make


@pytest.fixture
def make_callback_update():
    """Factory for mock Update with a callback_query."""
    def _make(data: str):
        query = AsyncMock()
        query.data = data
        query.message = MagicMock()
        query.message.chat_id = 12345

        update = MagicMock()
        update.callback_query = query
        update.effective_message = query.message
        return update
    return _make


@pytest.fixture
def make_command_update():
    """Factory for mock Update from a /command message."""
    def _make(text: str = "/start", user_id: int = 1):
        message = AsyncMock()
        message.text = text
        message.chat_id = 12345
        message.from_user = MagicMock()
        message.from_user.id = user_id

        update = MagicMock()
        update.message = message
        update.callback_query = None
        update.effective_message = message
        return update
    return _make

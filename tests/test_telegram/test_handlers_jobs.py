"""Tests for job list handlers."""

import pytest

from tycho.config import TychoConfig
from tycho.db import init_db
from tycho.telegram.handlers.jobs import (
    filter_score_callback,
    filter_status_callback,
    jobs_callback,
    jobs_command,
)


@pytest.mark.asyncio
class TestJobsCommand:
    async def test_shows_job_list(self, make_command_update, make_context):
        update = make_command_update("/jobs")
        ctx = make_context()
        await jobs_command(update, ctx)
        update.message.reply_text.assert_awaited_once()
        args = update.message.reply_text.call_args
        text = args[0][0]
        assert "Jobs" in text
        assert "page 1" in text
        # Should show 3 jobs (page_size=3, seeded 3)
        assert "ML Engineer" in text
        assert "Backend Developer" in text
        assert "Data Scientist" in text

    async def test_empty_database(self, make_command_update, make_context, tmp_path):
        """Test with no jobs in DB."""
        db_path = str(tmp_path / "empty.db")
        engine = init_db(db_path)
        config = TychoConfig(
            db_path=db_path,
            telegram={"enabled": True, "token": "t", "page_size": 3},
        )
        update = make_command_update("/jobs")
        ctx = make_context()
        ctx.bot_data = {"config": config, "engine": engine, "scheduler": None}
        await jobs_command(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "No jobs found" in text


@pytest.mark.asyncio
class TestJobsCallback:
    async def test_page_1(self, make_callback_update, make_context):
        update = make_callback_update("jobs:1::")
        ctx = make_context()
        await jobs_callback(update, ctx)
        update.callback_query.answer.assert_awaited_once()
        update.callback_query.edit_message_text.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "page 1" in text

    async def test_status_filter(self, make_callback_update, make_context):
        update = make_callback_update("jobs:1:interested:")
        ctx = make_context()
        await jobs_callback(update, ctx)
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "Backend Developer" in text
        # ML Engineer is status=new, should not appear
        assert "ML Engineer" not in text

    async def test_score_filter(self, make_callback_update, make_context):
        update = make_callback_update("jobs:1::0.75")
        ctx = make_context()
        await jobs_callback(update, ctx)
        text = update.callback_query.edit_message_text.call_args[0][0]
        # Only ML Engineer has score >= 0.75
        assert "ML Engineer" in text
        assert "Data Scientist" not in text

    async def test_pagination(self, make_callback_update, make_context):
        """With page_size=3, all 3 jobs fit on page 1. Page 2 should be empty."""
        update = make_callback_update("jobs:2::")
        ctx = make_context()
        await jobs_callback(update, ctx)
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "No jobs found" in text


@pytest.mark.asyncio
class TestFilterStatusCallback:
    async def test_shows_status_options(self, make_callback_update, make_context):
        update = make_callback_update("filter_status:1:")
        ctx = make_context()
        await filter_status_callback(update, ctx)
        update.callback_query.answer.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "status" in text.lower()


@pytest.mark.asyncio
class TestFilterScoreCallback:
    async def test_shows_score_options(self, make_callback_update, make_context):
        update = make_callback_update("filter_score:1:")
        ctx = make_context()
        await filter_score_callback(update, ctx)
        update.callback_query.answer.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "score" in text.lower()

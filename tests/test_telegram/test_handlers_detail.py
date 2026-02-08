"""Tests for job detail and status update handlers."""

import pytest

from tycho.db import get_job_by_prefix, get_session
from tycho.telegram.handlers.detail import (
    detail_callback,
    set_status_callback,
    status_menu_callback,
)


@pytest.mark.asyncio
class TestDetailCallback:
    async def test_shows_job_detail(self, make_callback_update, make_context):
        update = make_callback_update("detail:aaaaaaaa:1")
        ctx = make_context()
        await detail_callback(update, ctx)
        update.callback_query.answer.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "ML Engineer" in text
        assert "DeepTech AI" in text
        assert "0.85" in text

    async def test_job_not_found(self, make_callback_update, make_context):
        update = make_callback_update("detail:zzzzzzzz:1")
        ctx = make_context()
        await detail_callback(update, ctx)
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "not found" in text.lower()

    async def test_includes_url_button(self, make_callback_update, make_context):
        update = make_callback_update("detail:aaaaaaaa:1")
        ctx = make_context()
        await detail_callback(update, ctx)
        kwargs = update.callback_query.edit_message_text.call_args[1]
        keyboard = kwargs["reply_markup"]
        url_buttons = [
            btn for row in keyboard.inline_keyboard for btn in row if btn.url
        ]
        assert len(url_buttons) == 1
        assert url_buttons[0].url == "https://example.com/job/ml"

    async def test_default_page(self, make_callback_update, make_context):
        """detail:{job8} without page should default to 1."""
        update = make_callback_update("detail:aaaaaaaa:")
        ctx = make_context()
        await detail_callback(update, ctx)
        update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
class TestStatusMenuCallback:
    async def test_shows_status_choices(self, make_callback_update, make_context):
        update = make_callback_update("chstatus:aaaaaaaa:1")
        ctx = make_context()
        await status_menu_callback(update, ctx)
        update.callback_query.answer.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "status" in text.lower()
        # Check keyboard has all statuses
        kwargs = update.callback_query.edit_message_text.call_args[1]
        keyboard = kwargs["reply_markup"]
        callbacks = [
            btn.callback_data
            for row in keyboard.inline_keyboard
            for btn in row
            if btn.callback_data
        ]
        for s in ["new", "reviewed", "interested", "applied", "rejected", "archived"]:
            assert any(s in c for c in callbacks)


@pytest.mark.asyncio
class TestSetStatusCallback:
    async def test_updates_status(self, make_callback_update, make_context, seeded_db):
        update = make_callback_update("setstatus:aaaaaaaa:interested:1")
        ctx = make_context()
        await set_status_callback(update, ctx)

        # Verify DB was updated
        session = get_session(seeded_db)
        job, _ = get_job_by_prefix(session, "aaaaaaaa")
        session.close()
        assert job.status.value == "interested"

        # Verify answer toast shown
        update.callback_query.answer.assert_awaited()
        answer_text = update.callback_query.answer.call_args[0][0]
        assert "interested" in answer_text

        # Verify detail view re-rendered
        update.callback_query.edit_message_text.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "ML Engineer" in text

    async def test_status_job_not_found(self, make_callback_update, make_context):
        update = make_callback_update("setstatus:zzzzzzzz:applied:1")
        ctx = make_context()
        await set_status_callback(update, ctx)
        answer_text = update.callback_query.answer.call_args[0][0]
        assert "not found" in answer_text.lower()

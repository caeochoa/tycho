"""Tests for start/help/menu handlers."""

import pytest

from tycho.telegram.handlers.start import help_callback, menu_callback, start_command


@pytest.mark.asyncio
class TestStartCommand:
    async def test_sends_welcome_message(self, make_command_update, make_context):
        update = make_command_update("/start")
        ctx = make_context()
        await start_command(update, ctx)
        update.message.reply_text.assert_awaited_once()
        args = update.message.reply_text.call_args
        assert "Welcome to Tycho" in args[0][0]
        assert args[1]["parse_mode"] == "HTML"
        assert args[1]["reply_markup"] is not None


@pytest.mark.asyncio
class TestHelpCallback:
    async def test_via_callback_query(self, make_callback_update, make_context):
        update = make_callback_update("help")
        ctx = make_context()
        await help_callback(update, ctx)
        update.callback_query.answer.assert_awaited_once()
        update.callback_query.edit_message_text.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "/jobs" in text
        assert "/schedule" in text

    async def test_via_command(self, make_command_update, make_context):
        update = make_command_update("/help")
        # No callback_query for command
        update.callback_query = None
        ctx = make_context()
        await help_callback(update, ctx)
        update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
class TestMenuCallback:
    async def test_edits_to_welcome(self, make_callback_update, make_context):
        update = make_callback_update("menu")
        ctx = make_context()
        await menu_callback(update, ctx)
        update.callback_query.answer.assert_awaited_once()
        update.callback_query.edit_message_text.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "Welcome to Tycho" in text

"""Tests for schedule handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tycho.telegram.handlers.schedule import schedule_callback, schedule_trigger_callback


@pytest.mark.asyncio
class TestScheduleCallback:
    async def test_via_command(self, make_command_update, make_context):
        update = make_command_update("/schedule")
        update.callback_query = None
        ctx = make_context()
        await schedule_callback(update, ctx)
        update.message.reply_text.assert_awaited_once()
        text = update.message.reply_text.call_args[0][0]
        assert "Scheduler" in text

    async def test_via_callback(self, make_callback_update, make_context):
        update = make_callback_update("sched")
        ctx = make_context()
        await schedule_callback(update, ctx)
        update.callback_query.answer.assert_awaited_once()
        update.callback_query.edit_message_text.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "Scheduler" in text

    async def test_shows_disabled_when_disabled(self, make_callback_update, make_context):
        update = make_callback_update("sched")
        ctx = make_context()
        ctx.bot_data["config"].scheduler.enabled = False
        await schedule_callback(update, ctx)
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "Disabled" in text


@pytest.mark.asyncio
class TestScheduleTriggerCallback:
    async def test_successful_trigger(self, make_callback_update, make_context):
        update = make_callback_update("sched_trigger")
        ctx = make_context()

        mock_session = MagicMock()
        mock_session.close = MagicMock()

        call_count = 0

        async def smart_run_sync(func, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            func_name = getattr(func, "__name__", str(func))
            if func_name == "get_session":
                return mock_session
            if func_name == "get_schedule_runs":
                return []
            if func_name == "close":
                return None
            # trigger_now and others
            return None

        with patch("tycho.telegram.handlers.schedule.run_sync", side_effect=smart_run_sync):
            await schedule_trigger_callback(update, ctx)

        update.callback_query.answer.assert_awaited()
        # Should have been called at least twice: "Running..." then result
        assert update.callback_query.edit_message_text.await_count >= 2
        last_text = update.callback_query.edit_message_text.call_args_list[-1][0][0]
        assert "complete" in last_text.lower()

    async def test_trigger_failure(self, make_callback_update, make_context):
        update = make_callback_update("sched_trigger")
        ctx = make_context()

        call_count = 0

        async def fail_on_trigger(func, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            func_name = getattr(func, "__name__", str(func))
            if func_name == "trigger_now":
                raise RuntimeError("Connection failed")
            return None

        with patch("tycho.telegram.handlers.schedule.run_sync", side_effect=fail_on_trigger):
            await schedule_trigger_callback(update, ctx)

        calls = update.callback_query.edit_message_text.call_args_list
        assert any("failed" in str(c).lower() for c in calls)

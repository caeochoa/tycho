"""Tests for handler registration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tycho.telegram.bot import create_bot
from tycho.telegram.handlers import register_handlers


@pytest.mark.asyncio
class TestRegisterHandlers:
    async def test_registers_command_handlers(self, tg_config, seeded_db):
        app = await create_bot(tg_config, seeded_db)
        from telegram.ext import CommandHandler
        command_handlers = [h for h in app.handlers[0] if isinstance(h, CommandHandler)]
        commands = set()
        for h in command_handlers:
            commands.update(h.commands)
        assert "start" in commands
        assert "jobs" in commands
        assert "schedule" in commands
        assert "help" in commands

    async def test_registers_callback_handlers(self, tg_config, seeded_db):
        app = await create_bot(tg_config, seeded_db)
        from telegram.ext import CallbackQueryHandler
        callback_handlers = [h for h in app.handlers[0] if isinstance(h, CallbackQueryHandler)]
        # Should have handlers for: menu, help, noop, jobs, filter_status, filter_score,
        # detail, chstatus, setstatus, gen_exec, gen_opt, gen, sched_trigger, sched
        assert len(callback_handlers) >= 14

    async def test_unauthorized_handler_with_allowed_users(self, seeded_db):
        from tycho.config import TychoConfig
        config = TychoConfig(
            telegram={"enabled": True, "token": "test-token", "allowed_users": [111]},
        )
        app = await create_bot(config, seeded_db)
        from telegram.ext import MessageHandler
        msg_handlers = [h for h in app.handlers[0] if isinstance(h, MessageHandler)]
        assert len(msg_handlers) >= 1  # unauthorized catch-all

    async def test_no_unauthorized_handler_when_empty(self, tg_config, seeded_db):
        """When allowed_users is empty, no unauthorized catch-all is added."""
        app = await create_bot(tg_config, seeded_db)
        from telegram.ext import MessageHandler
        msg_handlers = [h for h in app.handlers[0] if isinstance(h, MessageHandler)]
        assert len(msg_handlers) == 0

    async def test_callback_protection_wrapper(self, seeded_db, make_callback_update):
        from tycho.config import TychoConfig
        from unittest.mock import AsyncMock
        
        config = TychoConfig(
            telegram={"enabled": True, "token": "test-token", "allowed_users": [123]},
        )
        app = await create_bot(config, seeded_db)
        
        # Get one callback handler (e.g., 'menu')
        from telegram.ext import CallbackQueryHandler
        menu_handler = next(h for h in app.handlers[0] 
                            if isinstance(h, CallbackQueryHandler) and h.pattern.pattern == "^menu$")
        
        # Unauthorized user (id 999)
        update = make_callback_update("menu")
        update.effective_user.id = 999
        context = MagicMock()
        
        await menu_handler.callback(update, context)
        
        # Should have answered with restriction message
        update.callback_query.answer.assert_awaited_once_with("Access restricted.", show_alert=True)
        
        # Authorized user (id 123)
        update.effective_user.id = 123
        update.callback_query.answer.reset_mock()
        
        # We need to mock the actual menu_callback because it's what's being wrapped
        with patch("tycho.telegram.handlers.start.menu_callback", new_callable=AsyncMock) as mock_menu:
             # This is tricky because the handler in 'app' already has the reference.
             # Let's just verify that it doesn't block the authorized user.
             # Since we can't easily swap the mock inside the closure, 
             # we check that answer wasn't called with "Access restricted"
             await menu_handler.callback(update, context)
             
             # If it passed the wrapper, it would call menu_callback which answers the query (without alert)
             # but here we just want to ensure it didn't call answer with the alert.
             # Note: menu_callback calls query.answer() without args.
             calls = update.callback_query.answer.await_args_list
             assert not any(c.args == ("Access restricted.",) for c in calls)

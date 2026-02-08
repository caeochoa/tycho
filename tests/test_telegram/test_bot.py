"""Tests for bot lifecycle."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tycho.config import TychoConfig
from tycho.telegram.bot import create_bot, start_bot, stop_bot


@pytest.mark.asyncio
class TestCreateBot:
    async def test_creates_application(self, tg_config, seeded_db):
        app = await create_bot(tg_config, seeded_db)
        assert app is not None
        assert app.bot_data["config"] is tg_config
        assert app.bot_data["engine"] is seeded_db

    async def test_raises_without_token(self, seeded_db):
        config = TychoConfig(telegram={"enabled": True, "token": ""})
        with pytest.raises(ValueError, match="token"):
            await create_bot(config, seeded_db)

    async def test_stores_scheduler(self, tg_config, seeded_db):
        scheduler = MagicMock()
        app = await create_bot(tg_config, seeded_db, scheduler=scheduler)
        assert app.bot_data["scheduler"] is scheduler

    async def test_registers_handlers(self, tg_config, seeded_db):
        app = await create_bot(tg_config, seeded_db)
        # Should have registered multiple handlers
        assert len(app.handlers[0]) > 0


@pytest.mark.asyncio
class TestStartStopBot:
    async def test_start_bot(self, tg_config, seeded_db):
        app = await create_bot(tg_config, seeded_db)

        with patch.object(app, "initialize", new_callable=AsyncMock) as mock_init, \
             patch.object(app, "start", new_callable=AsyncMock) as mock_start, \
             patch.object(app.updater, "start_polling", new_callable=AsyncMock) as mock_poll:
            await start_bot(app)
            mock_init.assert_awaited_once()
            mock_poll.assert_awaited_once()
            mock_start.assert_awaited_once()

    async def test_stop_bot(self, tg_config, seeded_db):
        app = await create_bot(tg_config, seeded_db)

        with patch.object(app.updater, "stop", new_callable=AsyncMock) as mock_ustop, \
             patch.object(app, "stop", new_callable=AsyncMock) as mock_stop, \
             patch.object(app, "shutdown", new_callable=AsyncMock) as mock_shutdown:
            await stop_bot(app)
            mock_ustop.assert_awaited_once()
            mock_stop.assert_awaited_once()
            mock_shutdown.assert_awaited_once()

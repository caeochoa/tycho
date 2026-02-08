"""Telegram bot application setup and lifecycle."""

import logging

from telegram.ext import Application

from tycho.config import TychoConfig
from tycho.telegram.handlers import register_handlers

logger = logging.getLogger(__name__)


async def create_bot(config: TychoConfig, engine, scheduler=None) -> Application:
    """Build the Telegram Application and register handlers."""
    token = config.telegram.effective_token
    if not token:
        raise ValueError("Telegram token not configured")

    app = Application.builder().token(token).build()

    # Store shared state in bot_data
    app.bot_data["config"] = config
    app.bot_data["engine"] = engine
    app.bot_data["scheduler"] = scheduler

    register_handlers(app, config.telegram.allowed_users)

    return app


async def start_bot(app: Application) -> None:
    """Initialize and start polling."""
    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    logger.info("Telegram bot started")


async def stop_bot(app: Application) -> None:
    """Stop polling and shut down."""
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    logger.info("Telegram bot stopped")

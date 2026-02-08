"""FastAPI application factory for Tycho web dashboard."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from tycho.config import load_config
from tycho.db import init_db

WEB_DIR = Path(__file__).parent
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB, config, and optionally start scheduler and Telegram bot."""
    config = load_config()
    engine = init_db(config.db_path)

    app.state.config = config
    app.state.engine = engine

    # Start scheduler if enabled
    scheduler = None
    if config.scheduler.enabled:
        try:
            from tycho.scheduler.scheduler import start_scheduler

            scheduler = start_scheduler(config, engine)
            app.state.scheduler = scheduler
        except Exception:
            pass

    # Start Telegram bot if enabled
    telegram_app = None
    if config.telegram.enabled:
        try:
            from tycho.telegram.bot import create_bot, start_bot

            token = config.telegram.effective_token
            if token:
                telegram_app = await create_bot(config, engine, scheduler=scheduler)
                await start_bot(telegram_app)
        except Exception as e:
            logger.warning("Telegram bot failed to start: %s", e)

    yield

    if telegram_app is not None:
        from tycho.telegram.bot import stop_bot

        await stop_bot(telegram_app)

    if scheduler is not None:
        from tycho.scheduler.scheduler import stop_scheduler

        stop_scheduler(scheduler)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Tycho", lifespan=lifespan)

    # Mount static files
    static_dir = WEB_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Register template engine on app state
    templates_dir = WEB_DIR / "templates"
    app.state.templates = Jinja2Templates(directory=str(templates_dir))

    # Include routers
    from tycho.web.routes import router

    app.include_router(router)

    return app

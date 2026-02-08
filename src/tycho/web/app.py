"""FastAPI application factory for Tycho web dashboard."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from tycho.config import load_config
from tycho.db import init_db

WEB_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB, config, and optionally start scheduler."""
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

    yield

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

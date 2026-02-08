"""FastAPI dependency injection for Tycho web dashboard."""

from typing import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from tycho.config import TychoConfig
from tycho.db import get_session as db_get_session


def get_config(request: Request) -> TychoConfig:
    """Get Tycho configuration from app state."""
    return request.app.state.config


def get_db(request: Request) -> Generator[Session, None, None]:
    """Get a database session, auto-closed after request."""
    session = db_get_session(request.app.state.engine)
    try:
        yield session
    finally:
        session.close()


def get_templates(request: Request):
    """Get Jinja2 templates from app state."""
    return request.app.state.templates


def get_llm_client(request: Request):
    """Get LLM client if available, or None."""
    config = get_config(request)
    if not config.llm.enabled:
        return None
    try:
        from tycho.llm import get_llm_client as _get_llm_client

        client = _get_llm_client(config.llm)
        if client.available:
            return client
    except Exception:
        pass
    return None

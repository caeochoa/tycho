"""Schedule management routes."""

import threading

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from tycho.config import TychoConfig
from tycho.db import get_schedule_runs
from tycho.web.deps import get_config, get_db, get_templates

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _get_scheduler(request: Request):
    """Get scheduler from app state, or None."""
    return getattr(request.app.state, "scheduler", None)


@router.get("", response_class=HTMLResponse)
async def schedule_index(
    request: Request,
    session: Session = Depends(get_db),
    config: TychoConfig = Depends(get_config),
):
    """Show schedule configuration and run history."""
    templates = get_templates(request)
    runs = get_schedule_runs(session, limit=20)
    scheduler = _get_scheduler(request)

    next_run = None
    if scheduler:
        from tycho.scheduler.scheduler import get_next_run_time

        next_run = get_next_run_time(scheduler)

    return templates.TemplateResponse(
        request,
        "schedule/index.html",
        {
            "request": request,
            "config": config,
            "runs": runs,
            "scheduler_active": scheduler is not None,
            "next_run": next_run,
        },
    )


@router.get("/status", response_class=HTMLResponse)
async def schedule_status(
    request: Request,
    session: Session = Depends(get_db),
    config: TychoConfig = Depends(get_config),
):
    """Return status partial for HTMX polling."""
    templates = get_templates(request)
    scheduler = _get_scheduler(request)

    next_run = None
    if scheduler:
        from tycho.scheduler.scheduler import get_next_run_time

        next_run = get_next_run_time(scheduler)

    runs = get_schedule_runs(session, limit=5)

    return templates.TemplateResponse(
        request,
        "schedule/_status.html",
        {
            "request": request,
            "scheduler_active": scheduler is not None,
            "next_run": next_run,
            "runs": runs,
        },
    )


@router.post("/trigger", response_class=HTMLResponse)
async def trigger_collection(
    request: Request,
    session: Session = Depends(get_db),
    config: TychoConfig = Depends(get_config),
):
    """Trigger immediate collection run in background thread."""
    templates = get_templates(request)
    engine = request.app.state.engine

    def _run():
        from tycho.scheduler.scheduler import trigger_now

        trigger_now(config, engine)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    runs = get_schedule_runs(session, limit=5)
    scheduler = _get_scheduler(request)
    next_run = None
    if scheduler:
        from tycho.scheduler.scheduler import get_next_run_time

        next_run = get_next_run_time(scheduler)

    return templates.TemplateResponse(
        request,
        "schedule/_status.html",
        {
            "request": request,
            "scheduler_active": scheduler is not None,
            "next_run": next_run,
            "runs": runs,
            "flash_message": "Collection triggered. Refresh status in a moment.",
        },
    )


@router.post("/update", response_class=HTMLResponse)
async def update_schedule(
    request: Request,
    cron: str = Form(...),
    config: TychoConfig = Depends(get_config),
):
    """Update the cron schedule (runtime only, does not persist to config.yaml)."""
    templates = get_templates(request)
    scheduler = _get_scheduler(request)

    if not scheduler:
        return HTMLResponse("<p>Scheduler is not running. Enable it in config.yaml.</p>")

    try:
        from tycho.scheduler.scheduler import reschedule, get_next_run_time

        reschedule(scheduler, cron)
        next_run = get_next_run_time(scheduler)

        return templates.TemplateResponse(
            request,
            "schedule/_status.html",
            {
                "request": request,
                "scheduler_active": True,
                "next_run": next_run,
                "runs": [],
                "flash_message": f"Schedule updated to: {cron}",
            },
        )
    except Exception as e:
        return HTMLResponse(f"<p class='flash-error'>Invalid cron: {e}</p>")

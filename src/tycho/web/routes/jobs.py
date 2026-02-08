"""Job listing and detail routes."""

import math

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from tycho.config import TychoConfig
from tycho.db import get_job_by_prefix, get_jobs_paginated, update_job_status
from tycho.web.deps import get_config, get_db, get_templates

router = APIRouter()

VALID_STATUSES = ["new", "reviewed", "interested", "applied", "rejected", "archived"]


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Redirect root to jobs list."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/jobs", status_code=302)


@router.get("/jobs", response_class=HTMLResponse)
async def job_list(
    request: Request,
    status: str | None = Query(None),
    min_score: float | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=5, le=100),
    sort: str = Query("score"),
    dir: str = Query("desc"),
    session: Session = Depends(get_db),
    config: TychoConfig = Depends(get_config),
):
    """List jobs with filtering and pagination."""
    templates = get_templates(request)
    offset = (page - 1) * per_page

    jobs, total = get_jobs_paginated(
        session,
        status=status,
        min_score=min_score,
        search=search,
        offset=offset,
        limit=per_page,
        sort_by=sort,
        sort_dir=dir,
    )

    total_pages = max(1, math.ceil(total / per_page))
    thresholds = config.scoring.thresholds

    ctx = {
        "request": request,
        "jobs": jobs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "status": status,
        "min_score": min_score,
        "search": search or "",
        "sort": sort,
        "dir": dir,
        "statuses": VALID_STATUSES,
        "thresholds": thresholds,
    }

    # HTMX partial vs full page
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "jobs/_table.html", ctx)
    return templates.TemplateResponse(request, "jobs/list.html", ctx)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(
    request: Request,
    job_id: str,
    session: Session = Depends(get_db),
    config: TychoConfig = Depends(get_config),
):
    """Show job detail with score breakdown."""
    templates = get_templates(request)
    job, error = get_job_by_prefix(session, job_id)

    if error:
        return templates.TemplateResponse(
            request,
            "jobs/detail.html",
            {"request": request, "job": None, "error": error, "statuses": VALID_STATUSES},
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "jobs/detail.html",
        {
            "request": request,
            "job": job,
            "error": None,
            "statuses": VALID_STATUSES,
            "thresholds": config.scoring.thresholds,
        },
    )


@router.post("/jobs/{job_id}/status", response_class=HTMLResponse)
async def update_status(
    request: Request,
    job_id: str,
    new_status: str = Form(...),
    session: Session = Depends(get_db),
    config: TychoConfig = Depends(get_config),
):
    """Update job status. Returns updated row partial for HTMX."""
    templates = get_templates(request)
    job, error = get_job_by_prefix(session, job_id)
    if error:
        return HTMLResponse(f"<tr><td colspan='7'>{error}</td></tr>", status_code=404)

    update_job_status(session, job.id, new_status)
    session.commit()

    # Re-fetch to get updated status
    job, _ = get_job_by_prefix(session, job.id)

    return templates.TemplateResponse(
        request,
        "jobs/_row.html",
        {
            "request": request,
            "job": job,
            "statuses": VALID_STATUSES,
            "thresholds": config.scoring.thresholds,
        },
    )


@router.post("/jobs/bulk-status", response_class=HTMLResponse)
async def bulk_update_status(
    request: Request,
    new_status: str = Form(...),
    session: Session = Depends(get_db),
    config: TychoConfig = Depends(get_config),
):
    """Bulk update job statuses. Returns updated table partial."""
    templates = get_templates(request)
    form = await request.form()
    job_ids = form.getlist("job_ids")

    for jid in job_ids:
        job, _ = get_job_by_prefix(session, jid)
        if job:
            update_job_status(session, job.id, new_status)
    session.commit()

    # Re-render full table with current filters
    from tycho.db import get_jobs_paginated

    jobs, total = get_jobs_paginated(session, limit=25)
    total_pages = max(1, math.ceil(total / 25))

    return templates.TemplateResponse(
        request,
        "jobs/_table.html",
        {
            "request": request,
            "jobs": jobs,
            "total": total,
            "page": 1,
            "per_page": 25,
            "total_pages": total_pages,
            "status": None,
            "min_score": None,
            "search": "",
            "sort": "score",
            "dir": "desc",
            "statuses": VALID_STATUSES,
            "thresholds": config.scoring.thresholds,
        },
    )

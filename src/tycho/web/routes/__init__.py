"""Aggregates all web route sub-routers."""

from fastapi import APIRouter

from tycho.web.routes.generate import router as generate_router
from tycho.web.routes.jobs import router as jobs_router
from tycho.web.routes.schedule import router as schedule_router

router = APIRouter()
router.include_router(jobs_router)
router.include_router(generate_router)
router.include_router(schedule_router)

"""APScheduler-based job collection scheduler."""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from tycho.config import TychoConfig
from tycho.db import get_known_source_ids, get_session, record_run, upsert_job

logger = logging.getLogger(__name__)

JOB_ID = "tycho_collection"


def collection_task(config: TychoConfig, engine):
    """Run the job collection pipeline. Same flow as CLI collect command."""
    session = get_session(engine)
    try:
        from tycho.collector.jobspy_collector import JobSpyCollector
        from tycho.collector.normalize import deduplicate
        from tycho.cv.profile_loader import load_profile
        from tycho.matcher.scorer import score_jobs

        collector = JobSpyCollector(
            country=config.search.country,
            location_countries=config.search.location_countries,
            linkedin_fetch_description=config.search.linkedin_fetch_description,
            max_age_days=config.search.max_age_days,
            known_ids=get_known_source_ids(session),
        )
        raw_jobs = collector.collect(
            search_terms=config.search.terms,
            locations=config.search.locations,
            results_wanted=config.search.results_per_source,
        )

        if config.companies:
            from tycho.collector.company_collector import collect_company_jobs

            raw_jobs.extend(collect_company_jobs(config))

        raw_count = len(raw_jobs)

        jobs = deduplicate(raw_jobs)
        deduped_count = len(jobs)

        # Score jobs
        try:
            profile = load_profile(config.profile_dir)
            jobs = score_jobs(jobs, profile, config.scoring)
        except Exception as e:
            logger.warning("Scoring failed during scheduled run: %s", e)

        # Store in database
        new_count = 0
        for job in jobs:
            if upsert_job(session, job):
                new_count += 1
        session.commit()

        record_run(
            session,
            raw_count=raw_count,
            deduped_count=deduped_count,
            new_count=new_count,
            error=(
                f"all {collector.searches_attempted} JobSpy searches failed"
                if collector.all_searches_failed is True
                else None
            ),
        )

        logger.info(
            "Scheduled collection: %d raw, %d deduped, %d new",
            raw_count,
            deduped_count,
            new_count,
        )

    except Exception as e:
        logger.error("Scheduled collection failed: %s", e)
        try:
            session.rollback()  # the session may be mid-failed-transaction
            record_run(session, error=str(e))
        except Exception:
            pass
    finally:
        session.close()


def parse_cron(cron_expr: str) -> dict:
    """Parse a cron expression into APScheduler CronTrigger kwargs."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def start_scheduler(config: TychoConfig, engine) -> BackgroundScheduler:
    """Start the background scheduler with collection task."""
    scheduler = BackgroundScheduler()
    cron_kwargs = parse_cron(config.scheduler.cron)

    scheduler.add_job(
        collection_task,
        trigger=CronTrigger(**cron_kwargs),
        args=[config, engine],
        id=JOB_ID,
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with cron: %s", config.scheduler.cron)
    return scheduler


def stop_scheduler(scheduler: BackgroundScheduler):
    """Shut down the scheduler gracefully."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


def reschedule(scheduler: BackgroundScheduler, cron_expr: str):
    """Update the cron schedule for the collection job."""
    cron_kwargs = parse_cron(cron_expr)
    scheduler.reschedule_job(JOB_ID, trigger=CronTrigger(**cron_kwargs))
    logger.info("Scheduler rescheduled with cron: %s", cron_expr)


def get_next_run_time(scheduler: BackgroundScheduler) -> datetime | None:
    """Get next scheduled run time."""
    job = scheduler.get_job(JOB_ID)
    if job:
        return job.next_run_time
    return None


def trigger_now(config: TychoConfig, engine):
    """Run collection immediately (not via scheduler)."""
    collection_task(config, engine)

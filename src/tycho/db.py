"""SQLite database via SQLAlchemy for job storage and tracking."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class JobRow(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)
    source_id = Column(String, default="")
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, default="")
    description = Column(Text, default="")
    url = Column(String, default="")
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_currency = Column(String, nullable=True)
    salary_interval = Column(String, nullable=True)
    date_posted = Column(DateTime, nullable=True)
    date_collected = Column(DateTime, default=datetime.now)
    tags = Column(Text, default="[]")  # JSON array
    score = Column(Float, nullable=True)
    score_details = Column(Text, nullable=True)  # JSON object
    status = Column(String, default="new")
    cv_path = Column(String, nullable=True)
    cover_letter_path = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_source_source_id"),
    )


class ScheduleRunRow(Base):
    __tablename__ = "schedule_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    raw_count = Column(Integer, default=0)
    deduped_count = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    status = Column(String, default="success")  # success, error
    error_message = Column(Text, nullable=True)


def get_engine(db_path: str = "tycho.db"):
    """Create SQLAlchemy engine."""
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(db_path: str = "tycho.db"):
    """Initialize database and create tables."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine) -> Session:
    """Create a new database session."""
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def job_to_row(job) -> JobRow:
    """Convert a Pydantic Job model to a database row."""
    return JobRow(
        id=job.id,
        source=job.source,
        source_id=job.source_id,
        title=job.title,
        company=job.company,
        location=job.location,
        description=job.description,
        url=job.url,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        salary_interval=job.salary_interval,
        date_posted=job.date_posted,
        date_collected=job.date_collected,
        tags=json.dumps(job.tags),
        score=job.score,
        score_details=json.dumps(job.score_details) if job.score_details else None,
        status=job.status.value,
        cv_path=job.cv_path,
        cover_letter_path=job.cover_letter_path,
        notes=job.notes,
    )


def row_to_job(row: JobRow):
    """Convert a database row to a Pydantic Job model."""
    from tycho.models import Job, JobStatus

    return Job(
        id=row.id,
        source=row.source,
        source_id=row.source_id,
        title=row.title,
        company=row.company,
        location=row.location,
        description=row.description,
        url=row.url,
        salary_min=row.salary_min,
        salary_max=row.salary_max,
        salary_currency=row.salary_currency,
        salary_interval=row.salary_interval,
        date_posted=row.date_posted,
        date_collected=row.date_collected,
        tags=json.loads(row.tags) if row.tags else [],
        score=row.score,
        score_details=json.loads(row.score_details) if row.score_details else None,
        status=JobStatus(row.status),
        cv_path=row.cv_path,
        cover_letter_path=row.cover_letter_path,
        notes=row.notes,
    )


def upsert_job(session: Session, job) -> bool:
    """Insert or update a job. Returns True if new, False if updated."""
    existing = (
        session.query(JobRow)
        .filter_by(source=job.source, source_id=job.source_id)
        .first()
    )
    if existing:
        # Update fields that may have changed
        existing.title = job.title
        existing.description = job.description
        existing.url = job.url
        existing.salary_min = job.salary_min
        existing.salary_max = job.salary_max
        existing.salary_currency = job.salary_currency
        existing.salary_interval = job.salary_interval
        if job.date_posted is not None:
            existing.date_posted = job.date_posted
        existing.tags = json.dumps(job.tags)
        # Refresh the score only when this collect actually scored the job,
        # so a run with scoring skipped doesn't wipe existing scores.
        if job.score is not None:
            existing.score = job.score
            existing.score_details = (
                json.dumps(job.score_details) if job.score_details else None
            )
        return False
    else:
        session.add(job_to_row(job))
        return True


def _max_age_filter(max_age_days: float):
    """Filter for jobs posted (or, if undated, collected) within the last N days."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    return func.coalesce(JobRow.date_posted, JobRow.date_collected) >= cutoff


def get_jobs(
    session: Session,
    status: str | None = None,
    min_score: float | None = None,
    limit: int = 100,
    max_age_days: float | None = None,
    location: str | None = None,
):
    """Query jobs with optional filters."""
    from tycho.models import Job

    query = session.query(JobRow)
    if status:
        query = query.filter(JobRow.status == status)
    if min_score is not None:
        query = query.filter(JobRow.score >= min_score)
    if max_age_days:
        query = query.filter(_max_age_filter(max_age_days))
    if location:
        query = query.filter(JobRow.location.ilike(f"%{location}%"))
    query = query.order_by(JobRow.score.desc().nullslast(), JobRow.date_collected.desc())
    rows = query.limit(limit).all()
    return [row_to_job(r) for r in rows]


def get_job_by_id(session: Session, job_id: str):
    """Get a single job by ID."""
    row = session.query(JobRow).filter_by(id=job_id).first()
    if row:
        return row_to_job(row)
    return None


def update_job_status(session: Session, job_id: str, status: str) -> bool:
    """Update job status. Returns True if found."""
    row = session.query(JobRow).filter_by(id=job_id).first()
    if row:
        row.status = status
        return True
    return False


def update_job_score(session: Session, job_id: str, score: float, details: dict | None = None):
    """Update job match score."""
    row = session.query(JobRow).filter_by(id=job_id).first()
    if row:
        row.score = score
        if details:
            row.score_details = json.dumps(details)


def update_job_paths(session: Session, job_id: str, cv_path: str | None = None, cover_letter_path: str | None = None):
    """Update generated file paths for a job."""
    row = session.query(JobRow).filter_by(id=job_id).first()
    if row:
        if cv_path:
            row.cv_path = cv_path
        if cover_letter_path:
            row.cover_letter_path = cover_letter_path


def get_jobs_paginated(
    session: Session,
    status: str | None = None,
    min_score: float | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 25,
    sort_by: str = "score",
    sort_dir: str = "desc",
    max_age_days: float | None = None,
) -> tuple[list, int]:
    """Query jobs with pagination. Returns (jobs, total_count)."""
    query = session.query(JobRow)
    count_query = session.query(func.count(JobRow.id))

    if status:
        query = query.filter(JobRow.status == status)
        count_query = count_query.filter(JobRow.status == status)
    if min_score is not None:
        query = query.filter(JobRow.score >= min_score)
        count_query = count_query.filter(JobRow.score >= min_score)
    if max_age_days:
        age_filter = _max_age_filter(max_age_days)
        query = query.filter(age_filter)
        count_query = count_query.filter(age_filter)
    if search:
        pattern = f"%{search}%"
        search_filter = (
            JobRow.title.ilike(pattern)
            | JobRow.company.ilike(pattern)
            | JobRow.location.ilike(pattern)
        )
        query = query.filter(search_filter)
        count_query = count_query.filter(search_filter)

    total = count_query.scalar()

    sort_column = getattr(JobRow, sort_by, JobRow.score)
    if sort_dir == "desc":
        query = query.order_by(sort_column.desc().nullslast(), JobRow.date_collected.desc())
    else:
        query = query.order_by(sort_column.asc().nullsfirst(), JobRow.date_collected.desc())

    rows = query.offset(offset).limit(limit).all()
    return [row_to_job(r) for r in rows], total


def get_job_by_prefix(session: Session, prefix: str):
    """Find a single job by ID or prefix. Returns (job, error_msg)."""
    job = get_job_by_id(session, prefix)
    if job:
        return job, None

    rows = session.query(JobRow).filter(JobRow.id.like(f"{prefix}%")).all()
    if len(rows) == 1:
        return row_to_job(rows[0]), None
    elif len(rows) > 1:
        matches = [(r.id[:8], r.title, r.company) for r in rows[:5]]
        return None, f"Ambiguous prefix '{prefix}': {matches}"
    return None, f"Job not found: {prefix}"


def get_schedule_runs(session: Session, limit: int = 20) -> list:
    """Get recent schedule runs."""
    rows = (
        session.query(ScheduleRunRow)
        .order_by(ScheduleRunRow.timestamp.desc())
        .limit(limit)
        .all()
    )
    return rows


def add_schedule_run(
    session: Session,
    raw_count: int = 0,
    deduped_count: int = 0,
    new_count: int = 0,
    status: str = "success",
    error_message: str | None = None,
) -> ScheduleRunRow:
    """Record a schedule run."""
    run = ScheduleRunRow(
        raw_count=raw_count,
        deduped_count=deduped_count,
        new_count=new_count,
        status=status,
        error_message=error_message,
    )
    session.add(run)
    return run


def get_known_source_ids(session: Session) -> dict[str, set[str]]:
    """Map source -> source_ids already stored *with a description*.

    Jobs stored with an empty description (e.g. a rate-limited LinkedIn fetch)
    are deliberately excluded so the next collect retries them.
    """
    known: dict[str, set[str]] = {}
    rows = session.query(JobRow.source, JobRow.source_id).filter(
        JobRow.source_id != "",
        JobRow.description.isnot(None),
        func.length(func.trim(JobRow.description)) > 0,
    )
    for source, source_id in rows:
        known.setdefault(source, set()).add(source_id)
    return known


def record_run(
    session: Session,
    raw_count: int = 0,
    deduped_count: int = 0,
    new_count: int = 0,
    error: str | None = None,
) -> ScheduleRunRow:
    """Write and commit a success (error is None) or error schedule_runs row."""
    run = add_schedule_run(
        session,
        raw_count=raw_count,
        deduped_count=deduped_count,
        new_count=new_count,
        status="error" if error is not None else "success",
        error_message=error,
    )
    session.commit()
    return run

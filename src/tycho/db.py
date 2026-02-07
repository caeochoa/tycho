"""SQLite database via SQLAlchemy for job storage and tracking."""

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    String,
    Text,
    UniqueConstraint,
    create_engine,
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
        existing.tags = json.dumps(job.tags)
        return False
    else:
        session.add(job_to_row(job))
        return True


def get_jobs(
    session: Session,
    status: str | None = None,
    min_score: float | None = None,
    limit: int = 100,
):
    """Query jobs with optional filters."""
    from tycho.models import Job

    query = session.query(JobRow)
    if status:
        query = query.filter(JobRow.status == status)
    if min_score is not None:
        query = query.filter(JobRow.score >= min_score)
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

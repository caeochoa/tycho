"""Job data normalization and deduplication."""

import hashlib
import re

from tycho.models import Job


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_company(company: str) -> str:
    """Normalize company name for dedup."""
    company = normalize_text(company)
    # Remove common suffixes
    for suffix in [" inc", " inc.", " ltd", " ltd.", " llc", " s.a.", " s.l.", " gmbh", " plc"]:
        if company.endswith(suffix):
            company = company[: -len(suffix)]
    return company.strip()


def dedup_key(job: Job) -> str:
    """Generate a deduplication key for a job."""
    parts = [
        normalize_company(job.company),
        normalize_text(job.title),
        normalize_text(job.location),
    ]
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()


def deduplicate(jobs: list[Job]) -> list[Job]:
    """Remove duplicate jobs, keeping the one with the richest description."""
    seen: dict[str, Job] = {}

    for job in jobs:
        key = dedup_key(job)
        if key in seen:
            existing = seen[key]
            # Keep the one with the longer description
            if len(job.description) > len(existing.description):
                # Preserve the ID of the first one seen
                job.id = existing.id
                seen[key] = job
        else:
            seen[key] = job

    return list(seen.values())

"""Job-profile scoring algorithm."""

import re

from tycho.config import ScoringConfig
from tycho.matcher.keywords import extract_keywords
from tycho.models import Job, Profile


def score_job(job: Job, profile: Profile, config: ScoringConfig) -> tuple[float, dict]:
    """Score a job against a profile. Returns (score, details)."""
    weights = config.weights
    job_keywords = extract_keywords(job.description, profile)

    kw_score = _keyword_match_score(job_keywords, profile)
    title_score = _title_match_score(job.title, profile)
    skills_score = _skills_overlap_score(job_keywords, profile)
    loc_score = _location_match_score(job.location, profile)

    total = (
        weights.keyword_match * kw_score
        + weights.title_match * title_score
        + weights.skills_overlap * skills_score
        + weights.location_match * loc_score
    )

    details = {
        "keyword_match": round(kw_score, 3),
        "title_match": round(title_score, 3),
        "skills_overlap": round(skills_score, 3),
        "location_match": round(loc_score, 3),
        "job_keywords": job_keywords,
        "total": round(total, 3),
    }

    return round(total, 3), details


def _keyword_match_score(job_keywords: list[str], profile: Profile) -> float:
    """Percentage of job keywords found in profile skills."""
    if not job_keywords:
        return 0.0

    profile_skills = {s.name.lower() for s in profile.skills.technical}
    # Also include skill tags as matchable terms
    for s in profile.skills.technical:
        profile_skills.update(t.lower() for t in s.tags)

    matches = sum(1 for kw in job_keywords if kw in profile_skills)
    return matches / len(job_keywords)


def _title_match_score(job_title: str, profile: Profile) -> float:
    """Similarity between job title and profile titles/experience titles."""
    job_words = set(re.findall(r"\w+", job_title.lower()))
    if not job_words:
        return 0.0

    # Check against profile titles
    best_score = 0.0
    reference_titles = list(profile.personal.titles)
    for exp in profile.experience:
        reference_titles.append(exp.title)

    for title in reference_titles:
        title_words = set(re.findall(r"\w+", title.lower()))
        if not title_words:
            continue
        overlap = len(job_words & title_words)
        union = len(job_words | title_words)
        score = overlap / union if union else 0.0
        best_score = max(best_score, score)

    return best_score


def _skills_overlap_score(job_keywords: list[str], profile: Profile) -> float:
    """Jaccard similarity of job required skills vs profile skills."""
    profile_skills = {s.name.lower() for s in profile.skills.technical}
    job_skills = set(job_keywords)

    if not job_skills and not profile_skills:
        return 0.0

    intersection = job_skills & profile_skills
    union = job_skills | profile_skills

    return len(intersection) / len(union) if union else 0.0


def _location_match_score(job_location: str, profile: Profile) -> float:
    """Binary match against preferred locations."""
    if not job_location:
        return 0.5  # Unknown location gets partial score

    job_loc = job_location.lower()

    # "remote" / "remoto" always matches
    if "remote" in job_loc or "remoto" in job_loc:
        return 1.0

    # Check against profile experience locations and personal info
    known_locations = ["madrid", "london", "edinburgh", "spain", "uk", "remote",
                       "remoto", "españa", "reino unido", "edimburgo", "londres"]
    for loc in known_locations:
        if loc in job_loc:
            return 1.0

    return 0.0


def score_jobs(jobs: list[Job], profile: Profile, config: ScoringConfig) -> list[Job]:
    """Score all jobs against the profile and return them with scores."""
    for job in jobs:
        score, details = score_job(job, profile, config)
        job.score = score
        job.score_details = details
    return jobs

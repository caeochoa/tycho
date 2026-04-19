"""Job-profile scoring algorithm."""

from __future__ import annotations

import re

from tycho.config import ScoringConfig
from tycho.matcher.keywords import extract_keywords
from tycho.models import Job, Profile


def score_job(
    job: Job, profile: Profile, config: ScoringConfig, llm_client=None
) -> tuple[float, dict]:
    """Score a job against a profile. Returns (score, details)."""
    weights = config.weights
    job_keywords = extract_keywords(job.description, profile, llm_client=llm_client)

    kw_score = _keyword_match_score(
        job_keywords, profile, config.min_keywords_confidence
    )
    title_score = _title_match_score(job.title, profile)
    skills_score = _skills_overlap_score(job_keywords, profile)
    loc_score = _location_match_score(job.location, config)

    total = (
        weights.keyword_match * kw_score
        + weights.title_match * title_score
        + weights.skills_overlap * skills_score
        + weights.location_match * loc_score
    )

    keyword_confidence = min(1.0, len(job_keywords) / config.min_keywords_confidence) if job_keywords else 0.0
    details = {
        "keyword_match": round(kw_score, 3),
        "keyword_confidence": round(keyword_confidence, 3),
        "title_match": round(title_score, 3),
        "skills_overlap": round(skills_score, 3),
        "location_match": round(loc_score, 3),
        "job_keywords": job_keywords,
        "total": round(total, 3),
    }

    return round(total, 3), details


def _keyword_match_score(
    job_keywords: list[str], profile: Profile, min_confidence_count: int = 8
) -> float:
    """Percentage of job keywords found in profile skills, scaled by extraction confidence.

    Jobs where few keywords were extracted (e.g. because their tech stack is outside
    the known keyword list) receive a confidence penalty so a 3/3 match on generic
    terms doesn't outscore a 10/15 match on a rich, well-described role.
    """
    if not job_keywords:
        return 0.0

    profile_skills = {s.name.lower() for s in profile.skills.technical}
    # Also include skill tags as matchable terms
    for s in profile.skills.technical:
        profile_skills.update(t.lower() for t in s.tags)

    matches = sum(1 for kw in job_keywords if kw in profile_skills)
    raw_score = matches / len(job_keywords)

    # Scale by confidence: fewer extracted keywords → lower confidence in the ratio
    confidence = min(1.0, len(job_keywords) / min_confidence_count)
    return raw_score * confidence


def _title_match_score(job_title: str, profile: Profile) -> float:
    """Profile-recall title match: fraction of *profile* title words found in the job title.

    Using profile-recall (overlap / profile_title_words) rather than Jaccard
    (overlap / union) means that a job title with extra seniority/context words
    (e.g. "Senior ML/AI Engineer – Agents Team") is not penalised for containing
    more words than the profile title ("AI Engineer"). A job that is missing
    profile title words is still penalised proportionally.
    """
    job_words = set(re.findall(r"\w+", job_title.lower()))
    if not job_words:
        return 0.0

    # Ignore common filler words that inflate job titles without adding signal
    STOPWORDS = {"senior", "junior", "lead", "staff", "principal", "associate",
                 "mid", "manager", "head", "director", "remote", "hybrid", "contract"}

    reference_titles = list(profile.personal.titles)
    for exp in profile.experience:
        reference_titles.append(exp.title)

    best_score = 0.0
    for title in reference_titles:
        profile_words = set(re.findall(r"\w+", title.lower())) - STOPWORDS
        if not profile_words:
            continue
        overlap = len(job_words & profile_words)
        score = overlap / len(profile_words)
        best_score = max(best_score, score)

    return best_score


def _skills_overlap_score(job_keywords: list[str], profile: Profile) -> float:
    """Profile recall: fraction of your *core* (priority-1) skills that the job requires.

    Using only priority-1 skills as the denominator keeps the baseline pool
    small (~8 skills) so that matching 6 of them scores 0.75 rather than being
    diluted by the full 29-skill profile list. Priority-2/3 skills can still
    contribute to the numerator if the job mentions them.
    """
    core_skills = {s.name.lower() for s in profile.skills.technical if s.priority == 1}
    if not core_skills:
        # Fallback: use all skills if no priority-1 skills defined
        core_skills = {s.name.lower() for s in profile.skills.technical}
    if not core_skills:
        return 0.0

    job_skills = set(job_keywords)
    intersection = job_skills & core_skills

    return len(intersection) / len(core_skills)


def _location_match_score(job_location: str, config: ScoringConfig) -> float:
    """Binary match against preferred locations using word-boundary regex."""
    if not job_location:
        return 0.5  # Unknown location gets partial score

    loc_cfg = config.locations
    job_loc = job_location.lower()

    # Expand abbreviations (word-boundary match, e.g. standalone "ES" → "spain")
    for abbrev, full in loc_cfg.abbreviations.items():
        job_loc = re.sub(rf"\b{re.escape(abbrev)}\b", full.lower(), job_loc, flags=re.IGNORECASE)

    # Check remote keywords with word boundaries
    for kw in loc_cfg.remote_keywords:
        if re.search(rf"\b{re.escape(kw)}\b", job_loc, flags=re.IGNORECASE):
            return 1.0

    # Check all preferred locations (both lists) with word boundaries
    all_preferred = loc_cfg.preferred + loc_cfg.preferred_es
    for loc in all_preferred:
        if re.search(rf"\b{re.escape(loc)}\b", job_loc, flags=re.IGNORECASE):
            return 1.0

    return 0.0


def score_jobs(
    jobs: list[Job], profile: Profile, config: ScoringConfig, llm_client=None
) -> list[Job]:
    """Score all jobs against the profile and return them with scores."""
    for job in jobs:
        score, details = score_job(job, profile, config, llm_client=llm_client)
        job.score = score
        job.score_details = details
    return jobs

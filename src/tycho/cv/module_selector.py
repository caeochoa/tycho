"""Select and rank profile modules for a specific job.

Phase 1: Tag-based selection only.
Phase 2: LLM rewriting of bullets and summary.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel as PydanticBaseModel

from tycho.matcher.keywords import extract_keywords
from tycho.models import (
    Bullet,
    EducationModule,
    ExperienceModule,
    Job,
    Language,
    OtherModule,
    Profile,
    TailoredBullet,
    TailoredEntry,
    TailoredProfile,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM rewrite schemas
# ---------------------------------------------------------------------------


class RewrittenBullets(PydanticBaseModel):
    bullets: list[str]


class RewrittenSummary(PydanticBaseModel):
    summary: str


# ---------------------------------------------------------------------------
# LLM rewrite helpers
# ---------------------------------------------------------------------------


def _llm_rewrite_bullets(
    llm_client,
    bullets: list[str],
    job_title: str,
    job_company: str,
    job_description: str,
) -> list[str]:
    """Rewrite selected bullets to match job language. Falls back to originals on any failure."""
    if not bullets:
        return bullets
    prompt = f"""You are tailoring a CV for a job application.

Job: {job_title} at {job_company}
Description excerpt:
{(job_description or "")[:600]}

Rewrite each bullet point to better match this role's language and emphasis.

Rules:
- Do not invent facts, metrics, tools, or achievements not in the original
- Preserve all quantitative claims exactly (e.g. "<20ms", "20+ projects")
- Use vocabulary from the job description where it fits naturally
- Keep bullets concise (1-2 lines max)
- Return exactly {len(bullets)} bullets in the same order

Bullets:
{chr(10).join(f'{i+1}. {b}' for i, b in enumerate(bullets))}
"""
    result = llm_client.invoke_structured(prompt, RewrittenBullets)
    if len(result.bullets) != len(bullets):
        return bullets  # fallback: wrong count
    return result.bullets


def _llm_rewrite_summary(
    llm_client,
    summary: str,
    job_title: str,
    job_company: str,
    job_description: str,
) -> str:
    """Rewrite summary to match job. Falls back to original on any failure."""
    if not summary:
        return summary
    prompt = f"""You are tailoring a CV for a job application.

Job: {job_title} at {job_company}
Description excerpt:
{(job_description or "")[:600]}

Rewrite the following professional summary to better match this role.

Rules:
- Do not invent facts or experience not present in the original
- Keep it concise (2-4 sentences max)
- Use vocabulary from the job description where it fits naturally

Summary:
{summary}
"""
    result = llm_client.invoke_structured(prompt, RewrittenSummary)
    return result.summary or summary


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def select_modules(
    profile: Profile,
    job: Job,
    language: str = "en",
    max_bullets_per_entry: int = 4,
    llm_client=None,
) -> TailoredProfile:
    """Select and tailor profile modules for a specific job."""
    job_keywords = set(extract_keywords(job.description, profile, llm_client=llm_client))

    # Select summary variation
    summary = _select_summary(profile)

    # Optionally rewrite summary with LLM
    if llm_client is not None and getattr(llm_client, "available", False):
        try:
            summary = _llm_rewrite_summary(
                llm_client, summary, job.title, job.company or "", job.description or ""
            )
        except Exception:
            logger.debug("LLM summary rewrite failed, using original", exc_info=True)

    # Select top skills relevant to job
    skills = _select_skills(profile, job_keywords)

    # Tailor experience entries
    experience = []
    for exp in profile.experience:
        if not exp.enabled:
            continue
        entry = _tailor_experience(exp, job_keywords, language, max_bullets_per_entry)
        if entry:
            if llm_client is not None and getattr(llm_client, "available", False):
                try:
                    rewritten = _llm_rewrite_bullets(
                        llm_client,
                        [b.text for b in entry.bullets],
                        job.title,
                        job.company or "",
                        job.description or "",
                    )
                    for bullet, new_text in zip(entry.bullets, rewritten):
                        bullet.text = new_text
                except Exception:
                    logger.debug("LLM bullet rewrite failed for experience entry, using originals", exc_info=True)
            experience.append(entry)

    # Tailor education entries
    education = []
    for edu in profile.education:
        if not edu.enabled:
            continue
        entry = _tailor_education(edu, job_keywords, language, max_bullets_per_entry)
        if entry:
            if llm_client is not None and getattr(llm_client, "available", False):
                try:
                    rewritten = _llm_rewrite_bullets(
                        llm_client,
                        [b.text for b in entry.bullets],
                        job.title,
                        job.company or "",
                        job.description or "",
                    )
                    for bullet, new_text in zip(entry.bullets, rewritten):
                        bullet.text = new_text
                except Exception:
                    logger.debug("LLM bullet rewrite failed for education entry, using originals", exc_info=True)
            education.append(entry)

    # Tailor other entries
    other = []
    for oth in profile.other:
        if not oth.enabled:
            continue
        entry = _tailor_other(oth, job_keywords, language, max_bullets_per_entry)
        if entry:
            if llm_client is not None and getattr(llm_client, "available", False):
                try:
                    rewritten = _llm_rewrite_bullets(
                        llm_client,
                        [b.text for b in entry.bullets],
                        job.title,
                        job.company or "",
                        job.description or "",
                    )
                    for bullet, new_text in zip(entry.bullets, rewritten):
                        bullet.text = new_text
                except Exception:
                    logger.debug("LLM bullet rewrite failed for other entry, using originals", exc_info=True)
            other.append(entry)

    # Use appropriate phone based on language
    personal = profile.personal

    return TailoredProfile(
        personal=personal,
        summary=summary,
        skills=skills,
        languages=profile.skills.languages,
        experience=experience,
        education=education,
        other=other,
        job_id=job.id,
        focus=None,
    )


# ---------------------------------------------------------------------------
# Summary / skills
# ---------------------------------------------------------------------------


def _select_summary(profile: Profile) -> str:
    """Select the best summary variation."""
    return profile.personal.summary


def _select_skills(profile: Profile, job_keywords: set[str]) -> list[str]:
    """Select and rank skills relevant to the job."""
    scored_skills = []
    for skill in profile.skills.technical:
        name_lower = skill.name.lower()
        # Score: keyword match + tag overlap + inverse priority
        kw_match = 1.0 if name_lower in job_keywords else 0.0
        tag_overlap = len(set(t.lower() for t in skill.tags) & job_keywords) / max(len(skill.tags), 1)
        priority_bonus = (4 - skill.priority) / 3  # priority 1 = 1.0, priority 3 = 0.33

        score = kw_match * 3 + tag_overlap + priority_bonus
        scored_skills.append((skill.name, score))

    scored_skills.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in scored_skills[:15]]


# ---------------------------------------------------------------------------
# Bullet scoring / text helpers
# ---------------------------------------------------------------------------


def _score_bullet(bullet: Bullet, job_keywords: set[str]) -> float:
    """Score a bullet by tag overlap with job keywords."""
    if not bullet.tags:
        return 0.0
    tag_overlap = len(set(t.lower() for t in bullet.tags) & job_keywords)
    priority_bonus = (4 - bullet.priority) / 3
    return tag_overlap + priority_bonus


def _get_bullet_text(bullet: Bullet, language: str) -> str:
    """Get the best text for a bullet based on language."""
    # Try language-specific text
    if language == "es" and bullet.text_es:
        return bullet.text_es

    return bullet.text


# ---------------------------------------------------------------------------
# Entry tailoring
# ---------------------------------------------------------------------------


def _tailor_experience(
    exp: ExperienceModule,
    job_keywords: set[str],
    language: str,
    max_bullets: int,
) -> TailoredEntry:
    """Tailor an experience entry for the job."""
    # Score and select bullets
    scored_bullets = [
        (b, _score_bullet(b, job_keywords)) for b in exp.bullets
    ]
    scored_bullets.sort(key=lambda x: x[1], reverse=True)
    selected = scored_bullets[:max_bullets]

    tailored_bullets = [
        TailoredBullet(
            text=_get_bullet_text(b, language),
            relevance_score=score,
        )
        for b, score in selected
    ]

    title = exp.title_es if language == "es" and exp.title_es else exp.title
    dates = exp.dates_es if language == "es" and exp.dates_es else exp.dates
    note = exp.note_es if language == "es" and exp.note_es else exp.note

    return TailoredEntry(
        id=exp.id,
        type="experience",
        title=title,
        organization=exp.company,
        dates=dates,
        location=exp.location,
        note=note,
        skills=exp.skills,
        bullets=tailored_bullets,
    )


def _tailor_education(
    edu: EducationModule,
    job_keywords: set[str],
    language: str,
    max_bullets: int,
) -> TailoredEntry:
    """Tailor an education entry for the job."""
    scored_bullets = [
        (b, _score_bullet(b, job_keywords)) for b in edu.bullets
    ]
    scored_bullets.sort(key=lambda x: x[1], reverse=True)
    selected = scored_bullets[:max_bullets]

    tailored_bullets = [
        TailoredBullet(
            text=_get_bullet_text(b, language),
            relevance_score=score,
        )
        for b, score in selected
    ]

    degree = edu.degree_es if language == "es" and edu.degree_es else edu.degree
    dates = edu.dates_es if language == "es" and edu.dates_es else edu.dates
    institution = edu.institution_es if language == "es" and edu.institution_es else edu.institution

    return TailoredEntry(
        id=edu.id,
        type="education",
        title=degree,
        organization=institution,
        dates=dates,
        location=edu.location,
        gpa=edu.gpa,
        skills=edu.skills,
        bullets=tailored_bullets,
    )


def _tailor_other(
    oth: OtherModule,
    job_keywords: set[str],
    language: str,
    max_bullets: int,
) -> TailoredEntry:
    """Tailor an 'other' entry for the job."""
    scored_bullets = [
        (b, _score_bullet(b, job_keywords)) for b in oth.bullets
    ]
    scored_bullets.sort(key=lambda x: x[1], reverse=True)
    selected = scored_bullets[:max_bullets]

    tailored_bullets = [
        TailoredBullet(
            text=_get_bullet_text(b, language),
            relevance_score=score,
        )
        for b, score in selected
    ]

    title = oth.title_es if language == "es" and oth.title_es else oth.title
    dates = oth.dates_es if language == "es" and oth.dates_es else oth.dates

    return TailoredEntry(
        id=oth.id,
        type="other",
        title=title,
        organization=oth.organization,
        dates=dates,
        location=oth.location,
        skills=oth.skills,
        bullets=tailored_bullets,
    )
